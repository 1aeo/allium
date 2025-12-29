"""
File: relays.py

Relays class object consisting of relays (list of dict) and onionoo fetch
timestamp
"""

import hashlib
import json
import multiprocessing as mp
import os
import re
import sys
import time
import urllib.request
from shutil import rmtree, copy2
from jinja2 import Environment, FileSystemLoader, FileSystemBytecodeCache
from .aroileaders import _calculate_aroi_leaderboards, _safe_parse_ip_address
from .progress import log_progress, get_memory_usage
from .progress_logger import ProgressLogger
from .string_utils import format_percentage_from_fraction
from .bandwidth_formatter import (
    BandwidthFormatter, 
    determine_unit, 
    get_divisor_for_unit, 
    format_bandwidth_with_unit,
    determine_unit_filter, 
    format_bandwidth_filter
)
import logging
import statistics
from datetime import datetime, timedelta

ABS_PATH = os.path.dirname(os.path.abspath(__file__))

# Bandwidth formatting utilities now imported from bandwidth_formatter.py

def is_private_ip_address(ip_str):
    """
    Compute-efficient helper function to determine if an IP address or CIDR range
    represents a private/local IP address that should not be counted as a meaningful
    restriction for exit relays. Uses safe IP parsing for validation and follows DRY principles.
    
    Detects private IPv4 ranges:
    - 0.0.0.0/8 (IANA special use - "this network")
    - 10.0.0.0/8 (10.x.x.x)
    - 127.0.0.0/8 (localhost)
    - 169.254.0.0/16 (link-local)
    - 172.16.0.0/12 (172.16.x.x - 172.31.x.x)
    - 192.168.0.0/16 (192.168.x.x)
    
    And private IPv6 ranges:
    - ::1 (localhost)
    - fc00::/7 (unique local addresses - fc00:: to fdff::)
    - fe80::/10 (link-local)
    
    Args:
        ip_str (str): IP address string, can include CIDR notation (e.g., "192.168.1.0/24")
    
    Returns:
        bool: True if the IP address/range is private/local, False if public
    """
    if not ip_str or ip_str == '*':
        return False  # Wildcard is not private
    
    # Remove CIDR notation if present
    ip_clean = ip_str.split('/')[0].strip()
    
    # Use safe IP parsing for validation and version detection
    parsed_ip, ip_version = _safe_parse_ip_address(ip_clean)
    
    if not parsed_ip:
        return False  # Invalid IP address, assume public
    
    # Import ipaddress module for proper range checking
    import ipaddress
    try:
        ip_obj = ipaddress.ip_address(parsed_ip)
        
        # Use Python's built-in private detection
        return ip_obj.is_private
        
    except Exception:
        return False  # If parsing fails, assume public


def parse_onionoo_timestamp(timestamp_str):
    """Parse Onionoo timestamp string into datetime object"""
    from datetime import datetime, timezone
    try:
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        return timestamp.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None

def create_time_thresholds():
    """Create common time threshold calculations used across the codebase"""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    return {
        'now': now,
        'day_ago': now - timedelta(days=1),
        'month_ago': now - timedelta(days=30),
        'six_months_ago': now - timedelta(days=180),
        'year_ago': now - timedelta(days=365)
    }

def format_timestamp_gmt(timestamp=None):
    """Format timestamp as GMT string for HTTP headers and display"""
    import time
    if timestamp is None:
        timestamp = time.time()
    return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(timestamp))

def format_time_ago(timestamp_str):
    """Format timestamp as multi-unit time ago (e.g., '2y 3m 2w ago')"""
    from datetime import timezone, datetime
    
    try:
        # Use centralized parsing
        timestamp = parse_onionoo_timestamp(timestamp_str)
        if timestamp is None:
            return "unknown"
            
        now = datetime.now(timezone.utc)
        
        # Calculate time difference
        diff = now - timestamp
        total_seconds = int(diff.total_seconds())
        
        if total_seconds < 0:
            return "in the future"
        
        # Time unit calculations
        years = total_seconds // (365 * 24 * 3600)
        remainder = total_seconds % (365 * 24 * 3600)
        
        months = remainder // (30 * 24 * 3600)
        remainder = remainder % (30 * 24 * 3600)
        
        weeks = remainder // (7 * 24 * 3600)
        remainder = remainder % (7 * 24 * 3600)
        
        days = remainder // (24 * 3600)
        remainder = remainder % (24 * 3600)
        
        hours = remainder // 3600
        remainder = remainder % 3600
        
        minutes = remainder // 60
        seconds = remainder % 60
        
        # Build the result with up to 3 largest units
        parts = []
        units = [
            (years, 'y'),
            (months, 'mo'),
            (weeks, 'w'),
            (days, 'd'),
            (hours, 'h'),
            (minutes, 'm'),
            (seconds, 's')
        ]
        
        # Take the 3 largest non-zero units
        for value, unit in units:
            if value > 0:
                parts.append(f"{value}{unit}")
            if len(parts) == 3:
                break
        
        if not parts:
            return "just now"
        
        return " ".join(parts) + " ago"
        
    except (ValueError, TypeError):
        return "unknown"

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

# Multiprocessing globals (initialized via fork for copy-on-write memory sharing)
_mp_relay_set = None
_mp_template = None


def _init_mp_worker(relay_set, template):
    """Initialize worker with shared data via fork"""
    global _mp_relay_set, _mp_template
    _mp_relay_set = relay_set
    _mp_template = template


def _render_page_mp(args):
    """Render single page in worker process"""
    html_path, template_args = args
    rendered = _mp_template.render(relays=_mp_relay_set, **template_args)
    with open(html_path, "w", encoding="utf8") as f:
        f.write(rendered)
    return True


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


def determine_ipv6_support(or_addresses):
    """
    Helper function to determine IPv6 support status based on or_addresses.
    Uses safe IP parsing for validation and follows DRY principles.
    
    Args:
        or_addresses (list): List of address:port strings from onionoo
        
    Returns:
        str: 'ipv4_only', 'ipv6_only', 'both', or 'none'
    """
    if not or_addresses:
        return 'none'
        
    has_ipv4 = False
    has_ipv6 = False
    
    for address in or_addresses:
        # Use safe IP parsing for validation and IP version detection
        parsed_ip, ip_version = _safe_parse_ip_address(address)
        
        if parsed_ip:  # Valid IP address parsed
            if ip_version == 4:
                has_ipv4 = True
            elif ip_version == 6:
                has_ipv6 = True
    
    if has_ipv4 and has_ipv6:
        return 'both'
    elif has_ipv4:
        return 'ipv4_only'
    elif has_ipv6:
        return 'ipv6_only'
    else:
        return 'none'

class Relays:
    """Relay class consisting of processing routines and onionoo data"""

    def __init__(self, output_dir, onionoo_url, relay_data, use_bits=False, progress=False, start_time=None, progress_step=0, total_steps=34, filter_downtime_days=7, base_url='', progress_logger=None, mp_workers=4):
        self.output_dir = output_dir
        self.onionoo_url = onionoo_url
        self.use_bits = use_bits
        self.progress = progress
        self.start_time = start_time or time.time()
        self.progress_step = progress_step
        self.total_steps = total_steps
        self.filter_downtime_days = filter_downtime_days
        self.base_url = base_url
        self.mp_workers = mp_workers  # 0 = disable, >0 = worker count
        self.ts_file = os.path.join(os.path.dirname(ABS_PATH), "timestamp")
        
        # Initialize bandwidth formatter with correct units setting
        self.bandwidth_formatter = BandwidthFormatter(use_bits=use_bits)
        
        # Use shared progress logger if provided, otherwise create new one
        # Shared logger ensures consistent step counting across allium.py and coordinator.py
        if progress_logger is not None:
            self.progress_logger = progress_logger
        else:
            self.progress_logger = ProgressLogger(self.start_time, self.progress_step, self.total_steps, self.progress)
        
        # Use provided relay data (fetched by coordinator)
        self.json = relay_data
        if self.json is None:
            return
        
        # Generate timestamp for compatibility - use centralized function
        self.timestamp = format_timestamp_gmt()

        self._filter_and_fix_relays()
        self._sort_by_observed_bandwidth()
        self._trim_platform()
        self._add_hashed_contact()
        self._process_aroi_contacts()  # Process AROI display info first
        self._preprocess_template_data()  # Pre-compute template optimization data
        self._categorize()  # Then build categories with processed relay objects
        self._generate_aroi_leaderboards()  # Generate AROI operator leaderboards
        self._generate_smart_context()  # Generate intelligence analysis (needed for CW/BW ratios)
        self._calculate_network_health_metrics()  # Calculate network health dashboard metrics (regenerated after uptime data)

    def _log_progress(self, message, increment_step=False):
        """Log progress message using shared progress utility"""
        # Use unified progress logger without incrementing (maintains backwards compatibility)
        self.progress_logger.log_without_increment(message)


    def _trim_platform(self):
        """
        Trim platform to retain base operating system without version number or
        unnecessary classification which could affect sorting

        e.g. "Tor 0.3.4.9 on Linux" -> "Linux"
        
        Also preserve the original platform information as platform_raw for display
        """
        for relay in self.json["relays"]:
            if relay.get("platform"):
                # Store the original platform information
                relay["platform_raw"] = relay["platform"]
                
                # Apply trimming to the platform field with error handling
                try:
                    # Try the standard format: "Tor x.x.x on Platform"
                    parts = relay["platform"].split(" on ", 1)
                    if len(parts) >= 2:
                        relay["platform"] = parts[1].split(" ")[0]
                        relay["platform"] = relay["platform"].split("/")[-1]  # GNU/*
                    else:
                        # Fallback: use the original platform string
                        relay["platform"] = relay["platform_raw"]
                except (IndexError, AttributeError):
                    # Fallback: use the original platform string
                    relay["platform"] = relay["platform_raw"]

    def _filter_and_fix_relays(self):
        """Filter relays by downtime and fix missing bandwidth - single efficient pass"""
        if not self.json or 'relays' not in self.json:
            return
        
        original_count = len(self.json["relays"])
        
        # Early exit if filtering disabled - just fix bandwidth
        if self.filter_downtime_days <= 0:
            for relay in self.json["relays"]:
                if not relay.get("observed_bandwidth"):
                    relay["observed_bandwidth"] = 0
            return
        
        # Combined filtering + bandwidth fix - single pass
        cutoff_time = datetime.utcnow() - timedelta(days=self.filter_downtime_days)
        
        def should_keep_relay(relay):
            # Fix bandwidth while we're processing
            if not relay.get("observed_bandwidth"):
                relay["observed_bandwidth"] = 0
            
            # Keep if running
            if relay.get('running', False):
                return True
            
            # For offline relays, check last_seen
            last_seen = relay.get('last_seen')
            if not last_seen:
                return False  # No last_seen data
            
            last_seen_dt = parse_onionoo_timestamp(last_seen)
            return last_seen_dt and last_seen_dt.replace(tzinfo=None) >= cutoff_time
        
        # Filter in-place
        self.json["relays"] = [r for r in self.json["relays"] if should_keep_relay(r)]
        
        # Log if relays were filtered
        excluded_count = original_count - len(self.json["relays"])
        if excluded_count > 0 and self.progress:
            self._log_progress(f"Filtered out {excluded_count} relays with downtime > {self.filter_downtime_days} days")

    def _simple_aroi_parsing(self, contact):
        """
        Extract AROI domain from contact information if conditions are met.
        For display purposes only - does not affect the stored/hashed contact info.
        More details: https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/
        
        According to the AROI spec, a valid contact string must have ALL 3:
        - ciissversion:2
        - proof:dns-rsa or proof:uri-rsa  
        - url:<domain>
        
        Args:
            contact: The contact string to process
        Returns:
            Tuple of (domain, aroi_field_status) where:
            - domain: extracted domain or "none" if incomplete
            - aroi_field_status: dict with presence of each field
        """
        if not contact:
            return "none"
            
        # Check if ALL required patterns are present (ciissversion, proof, and url)
        # Use word boundaries (\b) to avoid matching "donationurl:" or similar fields
        url_match = re.search(r'\burl:(?:https?://)?([^,\s]+)', contact, re.IGNORECASE)
        ciiss_match = re.search(r'\bciissversion:2\b', contact, re.IGNORECASE)
        proof_match = re.search(r'\bproof:(dns-rsa|uri-rsa)\b', contact, re.IGNORECASE)
        
        if url_match and ciiss_match and proof_match:
            # All 3 fields present - extract domain and clean it up
            domain = url_match.group(1)
            
            # Handle protocol URLs (e.g. https://domain.com/path)
            if '://' in domain:
                domain = domain.split('://', 1)[1]
            
            # Remove www. prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
                
            # Remove trailing slash and anything after first /
            domain = domain.split('/')[0]
            
            return domain
        
        return "none"

    def _process_aroi_contacts(self):
        """
        Process all relay contacts to extract AROI domain information.
        """
        for relay in self.json["relays"]:
            contact = relay.get("contact", "")
            # Extract AROI domain for new display format
            relay["aroi_domain"] = self._simple_aroi_parsing(contact)

    def _add_hashed_contact(self):
        """
        Adds a hashed contact key/value for every relay.
        Groups operators by AROI domain before hashing so that operators with the same
        AROI domain get a unified contact hash and single contact detail page.
        """
        from collections import defaultdict
        
        # Group relays by AROI domain (or individual contact for non-AROI)
        domain_to_relays = defaultdict(list)
        
        for idx, relay in enumerate(self.json["relays"]):
            contact = relay.get("contact", "")
            aroi_domain = self._simple_aroi_parsing(contact)
            
            # Use AROI domain as key if available, otherwise use contact hash as key
            if aroi_domain and aroi_domain != "none" and contact.strip():
                group_key = f"aroi_domain:{aroi_domain}"
            else:
                # Use contact string itself as key for individual operators
                group_key = f"individual_contact:{contact}"
            
            domain_to_relays[group_key].append((idx, relay, contact))
        
        # Create hashes for each group
        for group_key, relay_group in domain_to_relays.items():
            if group_key.startswith("aroi_domain:"):
                # AROI domain group - use unified hash based on domain
                unified_hash = hashlib.md5(group_key.encode("utf-8")).hexdigest()
            else:
                # Individual contact - use original contact string for hash
                _, contact = group_key.split(":", 1)
                unified_hash = hashlib.md5(contact.encode("utf-8")).hexdigest()
            
            # Apply hash to all relays in group
            for idx, relay, contact in relay_group:
                self.json["relays"][idx]["contact_md5"] = unified_hash

    def _preprocess_template_data(self):
        """
        Pre-process data for template rendering optimization.
        Uses centralized HTML escaping utilities to eliminate duplication.
        
        Pre-compute expensive Jinja2 operations to improve template performance:
        - HTML-escape contact strings (19.95% of template time)
        - HTML-escape flag strings (29.63% of template time) 
        - Lowercase flag strings (11.21% of template time)
        - Pre-split first_seen dates for display
        - Pre-computed percentage values for relay-info pages
        - Pre-computed bandwidth formatting
        - Pre-computed time formatting
        - Pre-computed address parsing
        """
        from .html_escape_utils import create_bulk_escaper, NA_FALLBACK, UNKNOWN_LOWERCASE
        
        # Use centralized HTML escaping utility
        bulk_escaper = create_bulk_escaper()
        
        # Pre-compute total network consensus weight for fallback fraction calculations
        # This is used when individual relays don't have consensus_weight_fraction from API
        self._total_network_cw = sum(
            relay.get('consensus_weight', 0) for relay in self.json["relays"]
        )
        
        for relay in self.json["relays"]:
            # Use centralized bulk escaping for all HTML escape patterns
            bulk_escaper.escape_all_relay_fields(relay)
            
            # Normalize country code to UPPERCASE for consistent URL generation
            # (matches RouteFluxMap's URL schema and sorted["country"] keys)
            if relay.get("country"):
                relay["country"] = relay["country"].upper()
            
            # Continue with non-HTML-escaping optimizations
            # Optimization 4: Pre-compute percentage values for relay-info templates
            # This avoids expensive format operations in individual relay pages
            # Use API-provided consensus_weight_fraction first, fallback to manual calculation
            if relay.get("consensus_weight_fraction") is not None:
                relay["consensus_weight_percentage"] = f"{relay['consensus_weight_fraction'] * 100:.2f}%"
            elif relay.get("consensus_weight") is not None and hasattr(self, '_total_network_cw') and self._total_network_cw > 0:
                # Fallback: compute fraction from raw consensus_weight
                computed_fraction = relay["consensus_weight"] / self._total_network_cw
                relay["consensus_weight_fraction"] = computed_fraction  # Store for consistency
                relay["consensus_weight_percentage"] = f"{computed_fraction * 100:.2f}%"
            else:
                relay["consensus_weight_percentage"] = NA_FALLBACK
                
            if relay.get("guard_probability") is not None:
                relay["guard_probability_percentage"] = f"{relay['guard_probability'] * 100:.2f}%"
            else:
                relay["guard_probability_percentage"] = NA_FALLBACK
                
            if relay.get("middle_probability") is not None:
                relay["middle_probability_percentage"] = f"{relay['middle_probability'] * 100:.2f}%"
            else:
                relay["middle_probability_percentage"] = NA_FALLBACK
                
            if relay.get("exit_probability") is not None:
                relay["exit_probability_percentage"] = f"{relay['exit_probability'] * 100:.2f}%"
            else:
                relay["exit_probability_percentage"] = NA_FALLBACK
                
            # Optimization 5: Pre-compute bandwidth formatting (major relay-list.html optimization)
            # This avoids calling _determine_unit and _format_bandwidth_with_unit in templates
            obs_bw = relay.get("observed_bandwidth", 0)
            obs_unit = self.bandwidth_formatter.determine_unit(obs_bw)
            obs_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(obs_bw, obs_unit)
            relay["obs_bandwidth_formatted"] = obs_formatted
            relay["obs_bandwidth_unit"] = obs_unit
            relay["obs_bandwidth_with_unit"] = f"{obs_formatted} {obs_unit}"
            
            # Optimization 6: Pre-compute time ago formatting (expensive function calls)
            if relay.get("last_restarted"):
                relay["last_restarted_ago"] = self._format_time_ago(relay["last_restarted"])
                relay["last_restarted_date"] = relay["last_restarted"].split(' ', 1)[0]
            else:
                relay["last_restarted_ago"] = UNKNOWN_LOWERCASE
                relay["last_restarted_date"] = UNKNOWN_LOWERCASE
                
            # Optimization 7: Pre-parse IP addresses using safe parsing for validation
            if relay.get("or_addresses") and len(relay["or_addresses"]) > 0:
                # Use safe IP parsing to extract IP address properly
                parsed_ip, _ = _safe_parse_ip_address(relay["or_addresses"][0])
                relay["ip_address"] = parsed_ip if parsed_ip else UNKNOWN_LOWERCASE
            else:
                relay["ip_address"] = UNKNOWN_LOWERCASE
                
            # Optimization 10: Pre-compute time formatting for relay-info pages
            if relay.get("first_seen"):
                relay["first_seen_ago"] = self._format_time_ago(relay["first_seen"])
            else:
                relay["first_seen_ago"] = UNKNOWN_LOWERCASE
                
            if relay.get("last_seen"):
                relay["last_seen_ago"] = self._format_time_ago(relay["last_seen"])
            else:
                relay["last_seen_ago"] = UNKNOWN_LOWERCASE
                
            # Optimization 11: Pre-compute uptime/downtime display based on last_restarted and running status
            relay["uptime_display"] = self._calculate_uptime_display(relay)
            
            # Initialize uptime API display (will be populated by _reprocess_uptime_data)
            relay["uptime_api_display"] = "0.0%/0.0%/0.0%/0.0%"
            
            # PERF: Pre-render flags HTML (eliminates nested Jinja2 loop - 50% speedup)
            # Template uses: {{ relay['_flags_html']|replace('{path}', page_ctx.path_prefix)|safe }}
            flags_lower = relay.get("flags_lower_escaped", [])
            flags_esc = relay.get("flags_escaped", [])
            relay["_flags_html"] = ''.join(
                f'<a href="{{path}}flag/{lo}/"><img src="{{path}}static/images/flags/{lo}.png" title="{esc}" alt="{esc}"></a>'
                for flag, lo, esc in zip(relay.get("flags", []), flags_lower, flags_esc)
                if flag != 'StaleDesc'
            )

    def _reprocess_uptime_data(self):
        """
        Optimized uptime data processing using consolidated single-pass analysis.
        This replaces the previous 3-pass approach with a single optimized loop
        through the uptime data that computes all metrics at once.
        
        Also calculates network-wide uptime percentiles once for all contact pages
        to avoid performance bottlenecks from recalculating for each contact.
        """
        uptime_data = getattr(self, 'uptime_data', None)
        if not uptime_data:
            return
            
        try:
            from .uptime_utils import process_all_uptime_data_consolidated
            
            # SINGLE PASS PROCESSING: Process all uptime data in one optimized loop
            # This replaces multiple separate loops with consolidated processing
            consolidated_results = process_all_uptime_data_consolidated(
                all_relays=self.json["relays"],
                uptime_data=uptime_data,
                include_flag_analysis=True
            )
            
            relay_uptime_data = consolidated_results['relay_uptime_data']
            network_statistics = consolidated_results['network_statistics']
            network_flag_statistics = consolidated_results.get('network_flag_statistics', {})
            
            # Store consolidated results for use by contact page processing
            self._consolidated_uptime_results = consolidated_results
            
            # Apply results to individual relays
            for relay in self.json["relays"]:
                fingerprint = relay.get('fingerprint', '')
                
                # Note: uptime_display was already calculated in _preprocess_template_data()
                # No need to recalculate here since uptime API doesn't modify running/last_restarted/last_seen
                
                # Apply uptime percentages from consolidated processing
                if fingerprint in relay_uptime_data:
                    relay["uptime_percentages"] = relay_uptime_data[fingerprint]['uptime_percentages']
                    # Store flag data for flag reliability analysis
                    relay["_flag_uptime_data"] = relay_uptime_data[fingerprint]['flag_data']
                else:
                    relay["uptime_percentages"] = {'1_month': 0.0, '6_months': 0.0, '1_year': 0.0, '5_years': 0.0}
                    relay["_flag_uptime_data"] = {}
            
            # Apply statistical coloring using consolidated network statistics
            self._apply_statistical_coloring(network_statistics)
            
            # Process flag uptime display data
            self._process_flag_uptime_display(network_flag_statistics)
            
        except Exception as e:
            # Fallback to basic processing if consolidated processing fails
            print(f"Warning: Consolidated uptime processing failed ({e}), falling back to basic processing")
            self._basic_uptime_processing()
            
        # PERFORMANCE OPTIMIZATION: Calculate network-wide uptime percentiles ONCE for all contacts
        # This avoids recalculating the same percentiles for every contact page (major performance optimization)
        uptime_data = getattr(self, 'uptime_data', None)
        if uptime_data:
            from .uptime_utils import calculate_network_uptime_percentiles
            self._log_progress("Calculating network uptime percentiles (6-month period)...")
            self.network_uptime_percentiles = calculate_network_uptime_percentiles(uptime_data, '6_months')
            if self.network_uptime_percentiles:
                total_relays = self.network_uptime_percentiles.get('total_relays', 0)
                self._log_progress(f"Network percentiles calculated: {total_relays:,} relays analyzed")
            else:
                self.network_uptime_percentiles = None
                self._log_progress("Network percentiles calculation failed: insufficient data")
        else:
            self.network_uptime_percentiles = None

    def _reprocess_bandwidth_data(self):
        """
        Process bandwidth data for contact page reliability metrics.
        Mirrors the uptime processing structure but handles bandwidth data separately.
        
        Calculates network-wide bandwidth percentiles and processes individual relay bandwidth data
        for use in contact page reliability metrics and flag bandwidth analysis.
        """
        bandwidth_data = getattr(self, 'bandwidth_data', None)
        if not bandwidth_data:
            return
        
        # Check if relay set is properly initialized before processing
        if not hasattr(self, 'json') or not self.json.get('relays'):
            self._log_progress("Skipping bandwidth processing: no relay data available")
            return
            
        try:
            # Use consolidated bandwidth processing with flag analysis
            from .bandwidth_utils import process_all_bandwidth_data_consolidated
            
            # SINGLE PASS PROCESSING: Process all bandwidth data in one optimized loop
            # This includes flag bandwidth analysis similar to uptime processing
            consolidated_results = process_all_bandwidth_data_consolidated(
                all_relays=self.json["relays"],
                bandwidth_data=bandwidth_data,
                include_flag_analysis=True
            )
            
            if not consolidated_results:
                return
            
            relay_bandwidth_data = consolidated_results['relay_bandwidth_data']
            network_flag_statistics = consolidated_results.get('network_flag_statistics', {})
            
            # Store consolidated results for use by contact page processing
            self._consolidated_bandwidth_results = consolidated_results
            
            # Apply results to individual relays
            for relay in self.json["relays"]:
                fingerprint = relay.get('fingerprint', '')
                
                # Apply bandwidth data from consolidated processing
                if fingerprint in relay_bandwidth_data:
                    relay["bandwidth_averages"] = relay_bandwidth_data[fingerprint]['bandwidth_averages']
                    # Store flag bandwidth data for flag bandwidth analysis
                    relay["_flag_bandwidth_data"] = relay_bandwidth_data[fingerprint]['flag_data']
                else:
                    relay["bandwidth_averages"] = {'6_months': 0.0, '1_year': 0.0, '5_years': 0.0}
                    relay["_flag_bandwidth_data"] = {}
            
            # Process flag bandwidth display data
            self._process_flag_bandwidth_display(network_flag_statistics)
            
            # Calculate network-wide bandwidth percentiles ONCE for all contacts
            self._log_progress("Calculating network bandwidth percentiles...")
            self.network_bandwidth_percentiles = self._calculate_network_bandwidth_percentiles(bandwidth_data)
            if self.network_bandwidth_percentiles:
                total_operators = self.network_bandwidth_percentiles.get('total_operators', 0)
                self._log_progress(f"Network bandwidth percentiles calculated: {total_operators:,} operators analyzed")
            else:
                self.network_bandwidth_percentiles = None
                self._log_progress("Network bandwidth percentiles calculation failed: insufficient data")
                
        except Exception as e:
            # Fallback gracefully if bandwidth processing fails
            print(f"Warning: Bandwidth processing failed ({e}), continuing without bandwidth metrics")
            self._consolidated_bandwidth_results = None
            self.network_bandwidth_percentiles = None

    def _reprocess_collector_data(self):
        """
        Process CollecTor consensus data for per-relay consensus evaluation.
        Attaches consensus troubleshooting information to each relay including:
        - Authority voting status
        - Flag eligibility analysis
        - Reachability information
        - Bandwidth measurements from authorities
        
        This follows the same pattern as _reprocess_uptime_data and _reprocess_bandwidth_data.
        """
        collector_data = getattr(self, 'collector_consensus_data', None)
        if not collector_data:
            return
        
        # Check if relay set is properly initialized before processing
        if not hasattr(self, 'json') or not self.json.get('relays'):
            self._log_progress("Skipping collector processing: no relay data available")
            return
        
        try:
            from .consensus import CollectorFetcher, format_relay_consensus_evaluation
            from .consensus.collector_fetcher import calculate_consensus_requirement, discover_authorities
            
            self._log_progress("Processing CollecTor consensus data for relay consensus evaluation...")
            
            # Get relay index and flag thresholds from collector data
            relay_index = collector_data.get('relay_index', {})
            flag_thresholds = collector_data.get('flag_thresholds', {})
            bw_authorities = collector_data.get('bw_authorities', [])
            
            if not relay_index:
                self._log_progress("No relay index in collector data, skipping consensus evaluation")
                return
            
            # Use the number of voting authorities from flag_thresholds (actual voters)
            # This is more accurate than counting Authority flags in relays
            # (some authorities like Serge may have the flag but not vote)
            authority_count = len(flag_thresholds) if flag_thresholds else 9
            
            # Also discover authorities from relay list for reference
            authorities = discover_authorities(self.json['relays'])
            
            # Calculate consensus requirement
            consensus_req = calculate_consensus_requirement(authority_count)
            
            # Store authority and threshold information for templates
            self.collector_authorities = authorities
            self.collector_flag_thresholds = flag_thresholds
            self.collector_bw_authorities = bw_authorities
            self.consensus_requirement = consensus_req
            
            # Create a CollectorFetcher instance with the pre-fetched data
            # to use its get_relay_consensus_evaluation method
            fetcher = CollectorFetcher()
            fetcher.relay_index = relay_index
            fetcher.flag_thresholds = flag_thresholds
            fetcher.bw_authorities = set(bw_authorities)
            fetcher.ipv6_testing_authorities = set(collector_data.get('ipv6_testing_authorities', []))
            
            # Process consensus evaluation for each relay
            evaluation_count = 0
            for relay in self.json["relays"]:
                fingerprint = relay.get('fingerprint', '').upper()
                if not fingerprint:
                    continue
                
                # Get raw consensus evaluation from fetcher
                raw_consensus_evaluation = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count)
                
                # Format for template display, passing current flags and observed_bandwidth
                # Note: observed_bandwidth (from descriptor) is the actual bandwidth for Guard eligibility
                # NOT the scaled consensus weight or vote Measured value
                current_flags = relay.get('flags', [])
                observed_bandwidth = relay.get('observed_bandwidth', 0)
                formatted_consensus_evaluation = format_relay_consensus_evaluation(
                    raw_consensus_evaluation, flag_thresholds, current_flags, observed_bandwidth,
                    use_bits=self.use_bits  # Pass use_bits for consistent bandwidth formatting
                )
                
                # Attach to relay
                relay['consensus_evaluation'] = formatted_consensus_evaluation
                
                if formatted_consensus_evaluation.get('available'):
                    evaluation_count += 1
            
            self._log_progress(f"Processed consensus evaluation for {evaluation_count} relays")
            
        except Exception as e:
            # Fallback gracefully if collector processing fails
            print(f"Warning: Collector data processing failed ({e}), continuing without consensus evaluation")
            import traceback
            traceback.print_exc()

    def _calculate_network_bandwidth_percentiles(self, bandwidth_data):
        """
        Calculate network-wide bandwidth percentiles for operator comparison.
        Mirrors the uptime percentile calculation but for bandwidth data.
        
        Args:
            bandwidth_data: Bandwidth data from Onionoo API
            
        Returns:
            dict: Network bandwidth percentiles or None if insufficient data
        """
        if not bandwidth_data or 'contact' not in self.json.get('sorted', {}):
            return None
            
        try:
            from .bandwidth_utils import extract_operator_daily_bandwidth_totals
            import statistics
            
            contacts = self.json['sorted']['contact']
            operator_bandwidth_values = []
            
            # Calculate 6-month average bandwidth for each operator
            for contact_hash, contact_data in contacts.items():
                if not contact_data.get('relays'):
                    continue
                    
                operator_relays = [self.json['relays'][i] for i in contact_data['relays']]
                
                # Use daily totals calculation (matches AROI leaderboard logic)
                daily_totals_result = extract_operator_daily_bandwidth_totals(
                    operator_relays, bandwidth_data, '6_months'
                )
                
                if daily_totals_result['daily_totals']:
                    avg_bandwidth = daily_totals_result['average_daily_total']
                    if avg_bandwidth > 0:  # Only include operators with actual bandwidth
                        operator_bandwidth_values.append(avg_bandwidth)
            
            if len(operator_bandwidth_values) < 10:  # Need minimum operators for percentiles
                return None
                
            # Calculate percentiles
            operator_bandwidth_values.sort()
            
            return {
                'percentile_5': statistics.quantiles(operator_bandwidth_values, n=20)[0],   # 5th percentile
                'percentile_25': statistics.quantiles(operator_bandwidth_values, n=4)[0],   # 25th percentile  
                'percentile_50': statistics.median(operator_bandwidth_values),              # Median
                'percentile_75': statistics.quantiles(operator_bandwidth_values, n=4)[2],   # 75th percentile
                'percentile_95': statistics.quantiles(operator_bandwidth_values, n=20)[18], # 95th percentile
                'total_operators': len(operator_bandwidth_values)
            }
            
        except Exception as e:
            print(f"Warning: Network bandwidth percentiles calculation failed: {e}")
            return None

    def _apply_statistical_coloring(self, network_statistics):
        """
        Apply statistical coloring to relay uptime percentages using pre-computed network statistics.
        
        Args:
            network_statistics (dict): Pre-computed network statistics for each time period
        """
        for relay in self.json["relays"]:
            percentages = relay.get("uptime_percentages", {})
            display_parts = []
            
            # Format as "96.7%/98.2%/93.2%/86.1%" with coloring
            for period in ['1_month', '6_months', '1_year', '5_years']:
                percentage = percentages.get(period, 0.0)
                percentage_str = f"{percentage:.1f}%"
                
                # Apply statistical coloring using pre-computed network statistics
                period_stats = network_statistics.get(period)
                if period_stats and percentage > 0:
                    # Green for perfect uptime (100.0%)
                    if percentage >= 100.0 or abs(percentage - 100.0) < 0.01:
                        percentage_str = f'<span style="color: #28a745;">{percentage_str}</span>'
                    # Red for low outliers (>2 std dev below mean)
                    elif percentage < period_stats['two_sigma_low']:
                        percentage_str = f'<span style="color: #dc3545;">{percentage_str}</span>'
                    # Green for high outliers (>2 std dev above mean)
                    elif percentage > period_stats['two_sigma_high']:
                        percentage_str = f'<span style="color: #28a745;">{percentage_str}</span>'
                    # Yellow for below-mean values
                    elif percentage < period_stats['mean']:
                        percentage_str = f'<span style="color: #cc9900;">{percentage_str}</span>'
                    else:
                        # Above mean but within normal range
                        percentage_str = f'<span style="color: #28a745;">{percentage_str}</span>'
                
                display_parts.append(percentage_str)
            
            # Join with forward slashes
            relay["uptime_api_display"] = "/".join(display_parts)
    
    def _process_flag_bandwidth_display(self, network_flag_statistics):
        """
        Process flag bandwidth data into display format with tooltips.
        
        Calculates flag-specific bandwidth display strings using priority system:
        Exit > Guard > Fast > Running flags. Only shows flags the relay actually has.
        
        Args:
            network_flag_statistics (dict): Network-wide flag statistics for comparison
        """
        # Flag priority mapping (Exit > Guard > Fast > Running)
        flag_priority = {'Exit': 1, 'Guard': 2, 'Fast': 3, 'Running': 4}
        flag_display_names = {
            'Exit': 'Exit Node',
            'Guard': 'Entry Guard', 
            'Fast': 'Fast Relay',
            'Running': 'Running Operation'
        }
        
        for relay in self.json["relays"]:
            # Get actual flags this relay has
            relay_flags = set(relay.get('flags', []))
            flag_data = relay.get("_flag_bandwidth_data", {})
            
            if not flag_data or not relay_flags:
                relay["flag_bandwidth_display"] = "N/A"
                relay["flag_bandwidth_tooltip"] = "No flag bandwidth data available"
                continue
            
            # Determine priority flag from flags the relay ACTUALLY HAS
            selected_flag = None
            best_priority = float('inf')
            
            for flag in flag_data.keys():
                # Only consider flags the relay actually has
                if flag in flag_priority and flag in relay_flags and flag_priority[flag] < best_priority:
                    selected_flag = flag
                    best_priority = flag_priority[flag]
            
            if not selected_flag or selected_flag not in flag_data:
                relay["flag_bandwidth_display"] = "N/A"
                relay["flag_bandwidth_tooltip"] = "No prioritized flag bandwidth data available"
                continue
            
            # Build display string with formatting
            display_parts = []
            tooltip_parts = []
            flag_display = flag_display_names[selected_flag]
            
            for period in ['6_months', '1_year', '5_years']:
                # Map to short period names for tooltip
                period_short = {'6_months': '6M', '1_year': '1Y', '5_years': '5Y'}[period]
                
                if period in flag_data[selected_flag] and flag_data[selected_flag][period] > 0:
                    bandwidth_val = flag_data[selected_flag][period]
                    data_points = 0  # Not tracked in simplified structure
                    
                    # Format bandwidth value
                    unit = self.bandwidth_formatter.determine_unit(bandwidth_val)
                    formatted_bw = self.bandwidth_formatter.format_bandwidth_with_unit(bandwidth_val, unit)
                    bandwidth_str = f"{formatted_bw} {unit}"
                    
                    # Apply FLAG BANDWIDTH color coding
                    color_class = ''
                    if (selected_flag in network_flag_statistics and 
                        period in network_flag_statistics[selected_flag] and
                        network_flag_statistics[selected_flag][period]):
                        
                        net_stats = network_flag_statistics[selected_flag][period]
                        
                        # Color coding based on statistical position
                        if bandwidth_val <= net_stats['two_sigma_low']:
                            color_class = 'statistical-outlier-low'
                        elif bandwidth_val > net_stats['two_sigma_high']:
                            color_class = 'statistical-outlier-high'
                        elif bandwidth_val < net_stats['mean']:
                            color_class = 'below-mean'
                        # High performance threshold (top 10% or above 2x mean)
                        elif bandwidth_val > net_stats['mean'] * 2:
                            color_class = 'high-performance'
                    
                    # Apply color styling based on class
                    if color_class == 'high-performance':
                        styled_bandwidth = f'<span style="color: #28a745; font-weight: bold;">{bandwidth_str}</span>'
                    elif color_class == 'statistical-outlier-low':
                        styled_bandwidth = f'<span style="color: #dc3545; font-weight: bold;">{bandwidth_str}</span>'
                    elif color_class == 'statistical-outlier-high':
                        styled_bandwidth = f'<span style="color: #28a745; font-weight: bold;">{bandwidth_str}</span>'
                    elif color_class == 'below-mean':
                        styled_bandwidth = f'<span style="color: #cc9900; font-weight: bold;">{bandwidth_str}</span>'
                    else:
                        styled_bandwidth = bandwidth_str
                    
                    display_parts.append(styled_bandwidth)
                    tooltip_parts.append(f"{period_short}: {bandwidth_str} ({data_points} data points)")
                else:
                    # No data for this period
                    display_parts.append("—")
                    tooltip_parts.append(f"{period_short}: No flag bandwidth data")
            
            # Store results
            relay["flag_bandwidth_display"] = "/".join(display_parts)
            # Generate tooltip in same format as flag reliability
            relay["flag_bandwidth_tooltip"] = f"{flag_display} flag bandwidth over time periods: " + ", ".join(tooltip_parts)
    
    def _process_flag_uptime_display(self, network_flag_statistics):
        """
        Process flag uptime data into display format with tooltips.
        
        Calculates flag-specific uptime display strings using priority system:
        Exit > Guard > Fast > Running flags. Only shows flags the relay actually has.
        Only displays flag uptime values when they differ from regular uptime.
        
        Args:
            network_flag_statistics (dict): Network-wide flag statistics for comparison
        """
        # Flag priority mapping (Exit > Guard > Fast > Running)
        flag_priority = {'Exit': 1, 'Guard': 2, 'Fast': 3, 'Running': 4}
        flag_display_names = {
            'Exit': 'Exit Node',
            'Guard': 'Entry Guard', 
            'Fast': 'Fast Relay',
            'Running': 'Running Operation'
        }
        
        for relay in self.json["relays"]:
            # Get actual flags this relay has
            relay_flags = set(relay.get('flags', []))
            flag_data = relay.get("_flag_uptime_data", {})
            
            if not flag_data or not relay_flags:
                relay["flag_uptime_display"] = "N/A"
                relay["flag_uptime_tooltip"] = "No flag uptime data available"
                continue
            
            # Determine priority flag from flags the relay ACTUALLY HAS
            selected_flag = None
            best_priority = float('inf')
            
            for flag in flag_data.keys():
                # Only consider flags the relay actually has
                if flag in flag_priority and flag in relay_flags and flag_priority[flag] < best_priority:
                    selected_flag = flag
                    best_priority = flag_priority[flag]
            
            if not selected_flag or selected_flag not in flag_data:
                relay["flag_uptime_display"] = "N/A"
                relay["flag_uptime_tooltip"] = "No prioritized flag data available"
                continue
            
            # Build display string with color coding and prefix
            display_parts = []
            tooltip_parts = []
            flag_display = flag_display_names[selected_flag]
            
            # Get regular uptime percentages for comparison
            regular_uptime = relay.get("uptime_percentages", {})
            
            for period in ['1_month', '6_months', '1_year', '5_years']:
                # Map to short period names for tooltip
                period_short = {'1_month': '1M', '6_months': '6M', '1_year': '1Y', '5_years': '5Y'}[period]
                
                if period in flag_data[selected_flag]:
                    uptime_val = flag_data[selected_flag][period]['uptime']
                    data_points = flag_data[selected_flag][period].get('data_points', 0)
                    
                    # Compare flag uptime with regular uptime before adding prefix
                    regular_uptime_val = regular_uptime.get(period, 0.0)
                    
                    # Only show flag uptime if it differs from regular uptime (allowing for small floating point differences)
                    if abs(uptime_val - regular_uptime_val) < 0.1:
                        # Values are essentially the same, skip showing flag uptime for this period
                        display_parts.append("—")  # Show dash to indicate "same as uptime"
                        tooltip_parts.append(f"{period_short}: Same as uptime ({uptime_val:.1f}%)")
                        continue
                    
                    # Format without prefix
                    percentage_str = f"{uptime_val:.1f}%"
                    
                    # Apply FLAG RELIABILITY color coding (not uptime color coding)
                    color_class = ''
                    
                    # Add network comparison for color determination
                    if (selected_flag in network_flag_statistics and 
                        period in network_flag_statistics[selected_flag] and
                        network_flag_statistics[selected_flag][period]):
                        
                        net_stats = network_flag_statistics[selected_flag][period]
                        net_mean = net_stats.get('mean', 0)
                        two_sigma_low = net_stats.get('two_sigma_low', 0)
                        two_sigma_high = net_stats.get('two_sigma_high', float('inf'))
                        
                        # Enhanced color coding logic matching flag reliability:
                        # Special handling for very low values (≤1%) - likely to be statistical outliers
                        if uptime_val <= 1.0:
                            colored_str = f'<span style="color: #dc3545;">{percentage_str}</span>'  # Red
                        elif uptime_val <= two_sigma_low:
                            colored_str = f'<span style="color: #dc3545;">{percentage_str}</span>'  # Red
                        elif uptime_val >= 99.0:
                            colored_str = f'<span style="color: #28a745;">{percentage_str}</span>'  # Green
                        elif uptime_val > two_sigma_high:
                            colored_str = f'<span style="color: #28a745;">{percentage_str}</span>'  # Green
                        elif uptime_val < net_mean:
                            colored_str = f'<span style="color: #cc9900;">{percentage_str}</span>'  # Yellow
                        else:
                            # Above mean but within normal range - no special coloring
                            colored_str = percentage_str
                    else:
                        # Fallback color coding when no network statistics available
                        if uptime_val <= 1.0:
                            colored_str = f'<span style="color: #dc3545;">{percentage_str}</span>'  # Red
                        elif uptime_val >= 99.0:
                            colored_str = f'<span style="color: #28a745;">{percentage_str}</span>'  # Green
                        else:
                            # Default: no special coloring
                            colored_str = percentage_str
                    
                    display_parts.append(colored_str)
                    
                    # Add network comparison for tooltip (if available)
                    network_comparison = ""
                    if (selected_flag in network_flag_statistics and 
                        period in network_flag_statistics[selected_flag] and
                        network_flag_statistics[selected_flag][period]):
                        
                        net_stats = network_flag_statistics[selected_flag][period]
                        net_mean = net_stats.get('mean', 0)
                        if net_mean > 0:
                            if uptime_val >= net_stats.get('two_sigma_high', float('inf')):
                                network_comparison = f" (exceptional vs network μ {net_mean:.1f}%)"
                            elif uptime_val <= net_stats.get('two_sigma_low', 0):
                                network_comparison = f" (low vs network μ {net_mean:.1f}%)"
                            elif uptime_val < net_mean:
                                network_comparison = f" (below network μ {net_mean:.1f}%)"
                            else:
                                network_comparison = f" (above network μ {net_mean:.1f}%)"
                    
                    tooltip_parts.append(f"{period_short}: {uptime_val:.1f}%{network_comparison}")
                else:
                    # No data for this period
                    display_parts.append("—")
                    tooltip_parts.append(f"{period_short}: No flag data")
            
            # Store results
            # If all periods show dashes (no differences), show "N/A" instead
            if all(part == "—" for part in display_parts):
                relay["flag_uptime_display"] = "Match"
                relay["flag_uptime_tooltip"] = f"{flag_display} flag uptime matches overall uptime across all periods"
            else:
                relay["flag_uptime_display"] = "/".join(display_parts)
                # Generate tooltip in same format as flag reliability
                relay["flag_uptime_tooltip"] = f"{flag_display} flag uptime over time periods: " + ", ".join(tooltip_parts)
    
    def _basic_uptime_processing(self):
        """
        Basic uptime processing fallback if consolidated processing fails.
        This maintains the original logic for compatibility.
        """
        for relay in self.json["relays"]:
            # Basic uptime/downtime display
            relay["uptime_display"] = self._calculate_uptime_display(relay)
            
            # Basic uptime percentages without statistical analysis
            uptime_percentages = {'1_month': 0.0, '6_months': 0.0, '1_year': 0.0, '5_years': 0.0}
            relay["uptime_percentages"] = uptime_percentages
            relay["uptime_api_display"] = "0.0%/0.0%/0.0%/0.0%"
            
            # Initialize flag uptime display for fallback processing
            relay["flag_uptime_display"] = "N/A"
            relay["flag_uptime_tooltip"] = "Uptime data processing failed"

    def _sort_by_observed_bandwidth(self):
        """
        Sort full JSON list by highest observed_bandwidth, retain this order
        during subsequent sorting (country, AS, etc)
        """
        self.json["relays"].sort(
            key=lambda x: x["observed_bandwidth"], reverse=True
        )

    def _write_timestamp(self):
        """
        Store encoded timestamp in a file to retain time of last request, passed
        to onionoo via If-Modified-Since header during fetch() if exists
        """
        timestamp = time.time()
        f_timestamp = format_timestamp_gmt(timestamp)
        if self.json is not None:
            with open(self.ts_file, "w", encoding="utf8") as ts_file:
                ts_file.write(f_timestamp)
        
        return f_timestamp

    def _calculate_network_totals(self):
        """
        Calculate network totals using three different relay counting methodologies:
        - Primary: Each relay counted once, Exit prioritized over Guard > Middle
        - Categories: Each relay counted once with separate Guard+Exit category  
        - All: Count relays in multiple roles (multi-role relays increment multiple counters)
        
        Returns consensus weight totals for backward compatibility.
        Caches all three count types in self.json['network_totals'].
        """
        # Initialize all three counting methods
        primary_counts = {"guard": 0, "middle": 0, "exit": 0, "total": 0}
        categories_counts = {"guard_only": 0, "middle": 0, "exit_only": 0, "guard_exit": 0, "total": 0}
        all_counts = {"guard": 0, "middle": 0, "exit": 0, "total": 0}
        
        # Consensus weight totals (for backward compatibility)
        total_guard_cw = 0
        total_middle_cw = 0  
        total_exit_cw = 0
        
        # Bandwidth totals (for CW/BW ratio calculations - optimization for intelligence_engine.py)
        total_network_bandwidth = 0
        total_guard_bandwidth = 0
        total_exit_bandwidth = 0
        
        # Bandwidth measured tracking
        measured_relays = 0
        
        for relay in self.json['relays']:
            flags = relay.get('flags', [])
            consensus_weight = relay.get('consensus_weight', 0)
            observed_bandwidth = relay.get('observed_bandwidth', 0)
            
            is_guard = 'Guard' in flags
            is_exit = 'Exit' in flags
            
            # Count relays measured by >= 3 bandwidth authorities
            if relay.get('measured') is True:
                measured_relays += 1
            
            # Bandwidth totals (new - for performance optimization)
            total_network_bandwidth += observed_bandwidth
            if is_guard:
                total_guard_bandwidth += observed_bandwidth
            if is_exit:
                total_exit_bandwidth += observed_bandwidth
            
            # Consensus weight calculations (existing logic - matches primary role assignment)
            if is_exit:
                total_exit_cw += consensus_weight
            elif is_guard:
                total_guard_cw += consensus_weight
            else:
                total_middle_cw += consensus_weight
                
            # Primary Role counting (Exit > Guard > Middle priority)
            if is_exit:
                primary_counts["exit"] += 1
            elif is_guard:
                primary_counts["guard"] += 1
            else:
                primary_counts["middle"] += 1
                
            # Role Categories counting (four mutually exclusive categories)
            if is_guard and is_exit:
                categories_counts["guard_exit"] += 1
            elif is_guard and not is_exit:
                categories_counts["guard_only"] += 1
            elif is_exit and not is_guard:
                categories_counts["exit_only"] += 1
            else:
                categories_counts["middle"] += 1
                
            # All Roles counting (multi-role relays increment multiple counters)
            if is_guard:
                all_counts["guard"] += 1
            if is_exit:
                all_counts["exit"] += 1
            if not is_guard and not is_exit:
                all_counts["middle"] += 1
        
        # Set totals
        total_relays = len(self.json['relays'])
        primary_counts["total"] = total_relays
        categories_counts["total"] = total_relays
        all_counts["total"] = total_relays
        
        # Cache all counting methods for template access
        self.json['network_totals'] = {
            # Backward compatibility (primary counts)
            'guard_count': primary_counts["guard"],
            'middle_count': primary_counts["middle"], 
            'exit_count': primary_counts["exit"],
            'total_relays': total_relays,
            
            # New: All three counting methods
            'primary': primary_counts,
            'categories': categories_counts,
            'all': all_counts,
            
            # Bandwidth measured statistics
            'measured_relays': measured_relays,
            'measured_percentage': round((measured_relays / total_relays * 100), 1) if total_relays > 0 else 0.0,
            
            # Consensus weights (unchanged)
            'guard_consensus_weight': total_guard_cw,
            'middle_consensus_weight': total_middle_cw,
            'exit_consensus_weight': total_exit_cw,
            
            # Bandwidth totals (new - for CW/BW ratio performance optimization)
            'total_network_bandwidth': total_network_bandwidth,
            'total_guard_bandwidth': total_guard_bandwidth,
            'total_exit_bandwidth': total_exit_bandwidth
        }
        
        return total_guard_cw, total_middle_cw, total_exit_cw

    def _sort(self, relay, idx, k, v, cw, cw_fraction):
        """
        Populate self.sorted dictionary with values from :relay:

        Args:
            relay: relay from which values are derived
            idx:   index at which the relay can be found in self.json['relays']
            k:     the name of the key to use in self.sorted
            v:     the name of the subkey to use in self.sorted[k]
            cw:    consensus weight for this relay (passed to avoid repeated extraction)
            cw_fraction: consensus weight fraction (API value preferred, computed fallback)
        """
        if not v or not re.match(r"^[A-Za-z0-9_-]+$", v):
            return

        if not k in self.json["sorted"]:
            self.json["sorted"][k] = dict()

        if not v in self.json["sorted"][k]:
            self.json["sorted"][k][v] = {
                "relays": list(),
                "bandwidth": 0,
                "guard_bandwidth": 0,
                "middle_bandwidth": 0,
                "exit_bandwidth": 0,
                "exit_count": 0,
                "guard_count": 0,
                "middle_count": 0,
                "consensus_weight": 0,
                "consensus_weight_fraction": 0.0,
                "guard_consensus_weight": 0,
                "middle_consensus_weight": 0,
                "exit_consensus_weight": 0,
                "unique_as_set": set(),  # Track unique AS numbers for families
                "measured_count": 0,  # Track measured relays for families and contacts
            }
            
            # Initialize country counting for contacts
            if k == "contact":
                self.json["sorted"][k][v]["country_counts"] = {}

        bw = relay["observed_bandwidth"]
        # Use the consensus weight passed from _categorize (no repeated dict lookup)
        self.json["sorted"][k][v]["relays"].append(idx)
        self.json["sorted"][k][v]["bandwidth"] += bw

        if "Exit" in relay["flags"]:
            self.json["sorted"][k][v]["exit_count"] += 1
            self.json["sorted"][k][v]["exit_bandwidth"] += bw
            self.json["sorted"][k][v]["exit_consensus_weight"] += cw
        elif "Guard" in relay["flags"]:
            self.json["sorted"][k][v]["guard_count"] += 1
            self.json["sorted"][k][v]["guard_bandwidth"] += bw
            self.json["sorted"][k][v]["guard_consensus_weight"] += cw
        else:
            self.json["sorted"][k][v]["middle_count"] += 1
            self.json["sorted"][k][v]["middle_bandwidth"] += bw
            self.json["sorted"][k][v]["middle_consensus_weight"] += cw

        # Add consensus weight tracking
        # Accumulate both raw consensus_weight and the fraction (API or computed)
        if relay.get("consensus_weight"):
            self.json["sorted"][k][v]["consensus_weight"] += relay["consensus_weight"]
        # Accumulate fraction - uses API value when available, computed fallback otherwise
        self.json["sorted"][k][v]["consensus_weight_fraction"] += cw_fraction

        if k == "as":
            # relay["country"] is already UPPERCASE from _preprocess_template_data()
            self.json["sorted"][k][v]["country"] = relay.get("country")
            self.json["sorted"][k][v]["country_name"] = relay.get("country_name") or relay.get("country", "")
            self.json["sorted"][k][v]["as_name"] = relay.get("as_name")
        
        if k == "country":
            # Set country name for countries - truncate to 32 characters as requested
            # relay["country"] is already UPPERCASE from _preprocess_template_data()
            full_country_name = relay.get("country_name") or relay.get("country", "")
            truncated_country_name = full_country_name[:32] if len(full_country_name) > 32 else full_country_name
            self.json["sorted"][k][v]["country_name"] = truncated_country_name
            self.json["sorted"][k][v]["country_name_full"] = full_country_name

        if k == "family" or k == "contact" or k == "country" or k == "platform" or k == "as":
            # Families, contacts, countries, platforms, and networks benefit from additional tracking data:
            # - Contact info and MD5 hash for linking
            # - AROI domain for display purposes  
            # - Unique AS tracking for network diversity analysis
            # - First seen date tracking (oldest relay in group)
            # - For countries, platforms, and networks: also track unique contacts and families
            if k == "country" or k == "platform" or k == "as":
                # Track unique contacts, families, and AROI domains for countries, platforms, and networks
                if not self.json["sorted"][k][v].get("unique_contact_set"):
                    self.json["sorted"][k][v]["unique_contact_set"] = set()
                if not self.json["sorted"][k][v].get("unique_family_set"):
                    self.json["sorted"][k][v]["unique_family_set"] = set()
                if not self.json["sorted"][k][v].get("unique_aroi_set"):
                    self.json["sorted"][k][v]["unique_aroi_set"] = set()
                if not self.json["sorted"][k][v].get("aroi_to_contact_map"):
                    self.json["sorted"][k][v]["aroi_to_contact_map"] = {}
                
                # Add this relay's contact hash to the country/platform/network's unique contacts
                # Use the pre-computed contact_md5 which includes unified AROI domain grouping
                c_hash = relay.get("contact_md5", "")
                if c_hash:
                    self.json["sorted"][k][v]["unique_contact_set"].add(c_hash)
                
                # Add this relay's AROI domain to the country/platform/network's unique AROI domains
                aroi_domain = relay.get("aroi_domain", "")
                if aroi_domain and aroi_domain != "none" and aroi_domain.strip():
                    self.json["sorted"][k][v]["unique_aroi_set"].add(aroi_domain)
                    # APPROACH 1 ENHANCEMENT: Build AROI-to-contact mapping during categorization
                    self.json["sorted"][k][v]["aroi_to_contact_map"][aroi_domain] = c_hash
                
                # Add this relay's family to the country/platform/network's unique families
                if relay.get("effective_family") and len(relay["effective_family"]) > 1:
                    # Use the first family member as the family identifier
                    family_id = relay["effective_family"][0]
                    self.json["sorted"][k][v]["unique_family_set"].add(family_id)
            if k == "family" or k == "contact" or k == "as":
                # Count measured relays
                if relay.get("measured"):
                    self.json["sorted"][k][v]["measured_count"] += 1 
            
            self.json["sorted"][k][v]["contact"] = relay.get("contact", "")
            self.json["sorted"][k][v]["contact_md5"] = relay.get("contact_md5", "")
            self.json["sorted"][k][v]["aroi_domain"] = relay.get("aroi_domain", "")
            
            # Track country counts for contacts (primary country calculation)
            # relay["country"] is already UPPERCASE from _preprocess_template_data()
            if k == "contact" and (country := relay.get("country")):
                self.json["sorted"][k][v]["country_counts"][country] = \
                    self.json["sorted"][k][v]["country_counts"].get(country, 0) + 1

            # Track unique AS numbers for this family/contact/country/platform/network
            relay_as = relay.get("as")
            if relay_as:
                self.json["sorted"][k][v]["unique_as_set"].add(relay_as)

            # update the first_seen parameter to always contain the oldest
            # relay's first_seen date
            if not self.json["sorted"][k][v].get("first_seen"):
                self.json["sorted"][k][v]["first_seen"] = relay["first_seen"]
            elif self.json["sorted"][k][v]["first_seen"] > relay["first_seen"]:
                self.json["sorted"][k][v]["first_seen"] = relay["first_seen"]

    def _categorize(self):
        """
        Iterate over self.json['relays'] set and call self._sort() against
        discovered relays with attributes we use to generate static sets
        """
        self.json["sorted"] = dict()
        
        # Initialize all expected categories to prevent template errors with small datasets
        expected_categories = ["as", "country", "platform", "flag", "family", "first_seen", "contact"]
        for category in expected_categories:
            self.json["sorted"][category] = dict()
        
        # Calculate comprehensive network totals once - replaces duplicate calculations
        total_guard_cw, total_middle_cw, total_exit_cw = self._calculate_network_totals()

        for idx, relay in enumerate(self.json["relays"]):
            # Extract consensus weight once per relay to avoid repeated dict lookups
            # This value gets used multiple times: once per _sort call + once for totals
            cw = relay.get("consensus_weight", 0)
            
            # Get relay's consensus weight fraction - prefer API value, fallback to computed
            # This ensures consistency with individual relay display
            api_fraction = relay.get("consensus_weight_fraction")
            if api_fraction is not None:
                cw_fraction = api_fraction
            elif hasattr(self, '_total_network_cw') and self._total_network_cw > 0:
                cw_fraction = cw / self._total_network_cw
            else:
                cw_fraction = 0.0

            # Sort by AS, country (already UPPERCASE from _preprocess_template_data), and platform
            self._sort(relay, idx, "as", relay.get("as"), cw, cw_fraction)
            self._sort(relay, idx, "country", relay.get("country"), cw, cw_fraction)
            self._sort(relay, idx, "platform", relay.get("platform"), cw, cw_fraction)

            for flag in relay["flags"]:
                self._sort(relay, idx, "flag", flag, cw, cw_fraction)

            if relay.get("effective_family"):
                for member in relay["effective_family"]:
                    if not len(relay["effective_family"]) > 1:
                        continue
                    self._sort(relay, idx, "family", member, cw, cw_fraction)

            self._sort(
                relay, idx, "first_seen", relay["first_seen"].split(" ")[0], cw, cw_fraction
            )

            # Use the pre-computed contact_md5 which includes unified AROI domain grouping
            c_hash = relay.get("contact_md5", "")
            self._sort(relay, idx, "contact", c_hash, cw, cw_fraction)

        # Calculate consensus weight fractions using the totals we accumulated above
        # This avoids a second full iteration through all relays
        self._calculate_consensus_weight_fractions(total_guard_cw, total_middle_cw, total_exit_cw)
        
        # Calculate family statistics immediately after categorization when data is fresh
        # This calculates both network totals and family-specific statistics for misc-families pages
        self._calculate_and_cache_family_statistics(total_guard_cw, total_middle_cw, total_exit_cw)
        
        # Convert unique AS sets to counts for families, contacts, countries, platforms, and networks
        self._finalize_unique_as_counts()
        
        # Calculate derived contact data: primary countries and bandwidth means
        self._calculate_contact_derived_data()
        
        # PERF OPTIMIZATION: Pre-compute display values to eliminate expensive Jinja2 calculations
        # This pre-computes formatted bandwidth, consensus weight, and relay count strings
        # for all sorted groups, reducing template render time by 30-40%
        self._precompute_display_values()
        
        # NOTE: _precompute_all_contact_page_data() is called from the coordinator
        # AFTER uptime data, bandwidth data, and AROI leaderboards are processed.
        # This is required because contact page data depends on those calculations.

    def _calculate_consensus_weight_fractions(self, total_guard_cw, total_middle_cw, total_exit_cw):
        """
        Calculate consensus weight fractions for guard, middle, and exit relays
        
        Args:
            total_guard_cw: Total consensus weight of all guard relays in the network
            total_middle_cw: Total consensus weight of all middle relays in the network  
            total_exit_cw: Total consensus weight of all exit relays in the network
            
        These totals are passed from _categorize to avoid re-iterating through all relays.
        """
        # Calculate total consensus weight for fallback fraction calculations
        total_consensus_weight = total_guard_cw + total_middle_cw + total_exit_cw
        
        # Calculate fractions for each group using the provided network-wide totals
        for k in self.json["sorted"]:
            for v in self.json["sorted"][k]:
                item = self.json["sorted"][k][v]
                
                # Overall consensus_weight_fraction is already accumulated from relay fractions
                # (using API values when available, computed fallback otherwise)
                # Only compute from raw values if accumulated fraction is 0 but raw weight exists
                if item["consensus_weight_fraction"] == 0.0 and item["consensus_weight"] > 0 and total_consensus_weight > 0:
                    item["consensus_weight_fraction"] = item["consensus_weight"] / total_consensus_weight
                
                # Guard/Middle/Exit fractions must be computed from raw values
                # (no API-provided role-specific fractions available)
                if total_guard_cw > 0:
                    item["guard_consensus_weight_fraction"] = item["guard_consensus_weight"] / total_guard_cw
                else:
                    item["guard_consensus_weight_fraction"] = 0.0
                    
                if total_middle_cw > 0:
                    item["middle_consensus_weight_fraction"] = item["middle_consensus_weight"] / total_middle_cw
                else:
                    item["middle_consensus_weight_fraction"] = 0.0
                    
                if total_exit_cw > 0:
                    item["exit_consensus_weight_fraction"] = item["exit_consensus_weight"] / total_exit_cw
                else:
                    item["exit_consensus_weight_fraction"] = 0.0
                
                # Pre-compute formatted percentage strings for template optimization
                # This avoids expensive Jinja2 format operations in misc listing templates
                item["consensus_weight_percentage"] = f"{item['consensus_weight_fraction'] * 100:.2f}%"
                item["guard_consensus_weight_percentage"] = f"{item['guard_consensus_weight_fraction'] * 100:.2f}%"
                item["middle_consensus_weight_percentage"] = f"{item['middle_consensus_weight_fraction'] * 100:.2f}%"
                item["exit_consensus_weight_percentage"] = f"{item['exit_consensus_weight_fraction'] * 100:.2f}%"

    def _calculate_and_cache_family_statistics(self, total_guard_cw, total_middle_cw, total_exit_cw):
        """
        Calculate family network totals and enhanced centralization risk statistics
        
        Optimized Python implementation of complex Jinja2 calculations for misc-families pages.
        Replaces expensive template loops with efficient deduplication logic.
        
        Enhanced with four-state family relationship analysis:
        - Standalone: No family relationships declared
        - Alleged Only: Family declared but not mutual
        - Effective Only: All family claims are mutual  
        - Mixed: Some mutual, some one-way relationships
        
        Args:
            total_guard_cw: Total consensus weight of all guard relays in the network
            total_middle_cw: Total consensus weight of all middle relays in the network  
            total_exit_cw: Total consensus weight of all exit relays in the network
            
        These totals are passed from _categorize to avoid re-iterating through all relays.
        """
        # Initialize four-state family relationship counters
        standalone_relays = 0
        alleged_only_relays = 0
        effective_only_relays = 0
        mixed_relays = 0
        
        # Analyze each relay's family relationship state
        for relay in self.json['relays']:
            # Effective family should exclude the relay's own fingerprint and be 2+ members for actual family
            effective_family = relay.get('effective_family', [])
            alleged_family = relay.get('alleged_family', [])
            
            # Remove self-reference from effective family and check if there are other members
            relay_fingerprint = relay.get('fingerprint', '')
            if relay_fingerprint in effective_family:
                effective_family = [fp for fp in effective_family if fp != relay_fingerprint]
            
            has_effective = len(effective_family) > 0
            has_alleged = len(alleged_family) > 0
            
            if not has_effective and not has_alleged:
                standalone_relays += 1
            elif not has_effective and has_alleged:
                alleged_only_relays += 1  
            elif has_effective and not has_alleged:
                effective_only_relays += 1
            else:  # has_effective and has_alleged
                mixed_relays += 1
        
        # Calculate family participation percentages
        total_relay_count = len(self.json['relays'])
        if total_relay_count > 0:
            standalone_percentage = f"{(standalone_relays / total_relay_count) * 100:.1f}"
            alleged_only_percentage = f"{(alleged_only_relays / total_relay_count) * 100:.1f}"
            effective_only_percentage = f"{(effective_only_relays / total_relay_count) * 100:.1f}"
            mixed_percentage = f"{(mixed_relays / total_relay_count) * 100:.1f}"
            effective_total_relays = effective_only_relays + mixed_relays
            effective_total_percentage = f"{(effective_total_relays / total_relay_count) * 100:.1f}"
        else:
            standalone_percentage = alleged_only_percentage = effective_only_percentage = mixed_percentage = effective_total_percentage = "0.0"
            effective_total_relays = 0
        
        # Calculate configuration health metrics
        total_family_declared = alleged_only_relays + effective_only_relays + mixed_relays
        if total_family_declared > 0:
            # Count allegations (from alleged_only + mixed relays)
            total_alleged_count = 0
            total_effective_count = 0
            
            for relay in self.json['relays']:
                alleged_family = relay.get('alleged_family', [])
                effective_family = relay.get('effective_family', [])
                
                if alleged_family:
                    total_alleged_count += len(alleged_family)
                if effective_family:
                    total_effective_count += len(effective_family)
            
            total_family_declarations = total_alleged_count + total_effective_count
            if total_family_declarations > 0:
                misconfigured_percentage = f"{(total_alleged_count / total_family_declarations) * 100:.1f}"
                configured_percentage = f"{(total_effective_count / total_family_declarations) * 100:.1f}"
            else:
                misconfigured_percentage = configured_percentage = "0.0"
        else:
            misconfigured_percentage = configured_percentage = "0.0"
        
        # Process existing family structure for all family metrics in single optimized loop
        # This replaces 3 separate deduplication loops with one efficient calculation
        largest_family_size = 0
        large_family_count = 0
        unique_families_count = 0
        
        if 'family' in self.json['sorted']:
            processed_fingerprints = set()
            
            # Process each family only once using deduplication (serves multiple metrics)
            for k, v in self.json['sorted']['family'].items():
                # Get first relay fingerprint to check if this family was already processed
                first_relay_idx = v['relays'][0]
                first_relay_fingerprint = self.json['relays'][first_relay_idx]['fingerprint']
                
                if first_relay_fingerprint not in processed_fingerprints:
                    # Count this as one unique family (for families_count and total_families)
                    unique_families_count += 1
                    
                    # Track actual relay count and largest family (existing logic)
                    family_size = len(v['relays'])
                    largest_family_size = max(largest_family_size, family_size)
                    
                    # Count families with 10+ relays (existing logic)
                    if family_size >= 10:
                        large_family_count += 1
                    
                    # Mark all relays in this family as processed
                    for r in v['relays']:
                        relay_fingerprint = self.json['relays'][r]['fingerprint']
                        processed_fingerprints.add(relay_fingerprint)
        
        # Cache enhanced family statistics
        self.json['family_statistics'] = {
            # Four-state relationship counts
            'standalone_relays': standalone_relays,
            'standalone_percentage': standalone_percentage,
            'alleged_only_relays': alleged_only_relays,
            'alleged_only_percentage': alleged_only_percentage,
            'effective_only_relays': effective_only_relays,
            'effective_only_percentage': effective_only_percentage,
            'mixed_relays': mixed_relays,
            'mixed_percentage': mixed_percentage,
            'effective_total_relays': effective_total_relays,
            'effective_total_percentage': effective_total_percentage,
            
            # Configuration health metrics
            'misconfigured_percentage': misconfigured_percentage,
            'configured_percentage': configured_percentage,
            
            # Existing centralization metrics
            'largest_family_size': largest_family_size,
            'large_family_count': large_family_count,
            
            # OPTIMIZED: Unique families count (calculated once, reused everywhere)
            'unique_families_count': unique_families_count
        }

    def _finalize_unique_as_counts(self):
        """
        Convert unique AS sets to counts for families, contacts, countries, platforms, and networks and clean up memory.
        This should be called after all family, contact, country, platform, and network data has been processed.
        """
        for category in ["family", "contact", "country", "platform", "as"]:
            if category in self.json["sorted"]:
                for key, data in self.json["sorted"][category].items():
                    if "unique_as_set" in data:
                        data["unique_as_count"] = len(data["unique_as_set"])
                        # Remove the set to save memory and avoid JSON serialization issues
                        del data["unique_as_set"]
                    else:
                        # Fallback in case unique_as_set wasn't initialized
                        data["unique_as_count"] = 0
                    
                    # Handle country, platform, and network-specific unique counts
                    if category == "country" or category == "platform" or category == "as":
                        # Handle family counts using the existing logic
                        if "unique_family_set" in data:
                            data["unique_family_count"] = len(data["unique_family_set"])
                            del data["unique_family_set"]
                        else:
                            data["unique_family_count"] = 0
                            
                        # APPROACH 1 SIMPLIFIED: Use already-built sets and mappings from _sort()
                        unique_aroi_domains = data.get("unique_aroi_set", set())
                        unique_contact_hashes = data.get("unique_contact_set", set())
                        # aroi_to_contact_map already built during _sort(), no need to rebuild
                        
                        # APPROACH 1: Simplified HTML generation from existing data
                        aroi_contact_html_items = []
                        used_contacts = set()
                        aroi_map = data.get("aroi_to_contact_map", {})
                        
                        # Add AROI domain links first
                        for aroi in sorted(unique_aroi_domains):
                            if aroi and aroi != "none":
                                contact_hash = aroi_map.get(aroi, "")
                                if contact_hash:
                                    # Use vanity URL if base_url is configured and domain is validated
                                    if self.base_url and hasattr(self, 'validated_aroi_domains') and aroi in self.validated_aroi_domains:
                                        aroi_contact_html_items.append(f'<a href="{self.base_url}/{aroi.lower()}/">{aroi}</a>')
                                    else:
                                        aroi_contact_html_items.append(f'<a href="../../contact/{contact_hash}/">{aroi}</a>')
                                    used_contacts.add(contact_hash)
                                else:
                                    aroi_contact_html_items.append(aroi)
                        
                        # Add non-AROI contact links (truncated to 8 characters)
                        for contact_hash in sorted(unique_contact_hashes):
                            if contact_hash and contact_hash not in used_contacts:
                                aroi_contact_html_items.append(f'<a href="../../contact/{contact_hash}/">{contact_hash[:8]}</a>')
                        
                        # Store results
                        data["unique_aroi_contact_html"] = ", ".join(aroi_contact_html_items)
                        data["unique_aroi_count"] = len(unique_aroi_domains)
                        data["unique_aroi_list"] = sorted(unique_aroi_domains)
                        data["unique_contact_count"] = len(unique_contact_hashes)
                        data["unique_contact_list"] = sorted(unique_contact_hashes)
                        
                        # Cleanup sets to save memory
                        data.pop("unique_contact_set", None)
                        data.pop("unique_aroi_set", None)

    def _calculate_contact_derived_data(self):
        """
        Calculate derived contact data: primary countries and bandwidth means in single pass.
        Optimized implementation combining both calculations for better performance.
        """
        if "contact" not in self.json["sorted"]:
            return
            
        for contact_hash, contact_data in self.json["sorted"]["contact"].items():
            # PRIMARY COUNTRIES CALCULATION (from _calculate_primary_countries)
            country_counts = contact_data.get("country_counts", {})
            
            if country_counts:
                # Sort countries by relay count (highest to lowest) and build final list in one pass
                sorted_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)
                primary_country_code, primary_country_relay_count = sorted_countries[0]
                total_relay_count = len(contact_data["relays"])
                
                # Build country list with names in single pass - reuse existing relay data
                # relay["country"] is already UPPERCASE from _preprocess_template_data()
                country_names = {}
                for relay_idx in contact_data["relays"]:
                    country = self.json["relays"][relay_idx].get("country")
                    if country and country not in country_names:
                        country_names[country] = self.json["relays"][relay_idx].get("country_name") or country
                
                # Build final data structure directly
                # primary_country_code is from country_counts keys which are already UPPERCASE
                primary_country_name = country_names.get(primary_country_code, primary_country_code)
                contact_data["primary_country_data"] = {
                    'country': primary_country_code,
                    'country_name': primary_country_name,
                    'relay_count': primary_country_relay_count,
                    'total_relays': total_relay_count,
                    'tooltip': f"All {total_relay_count} relays in {primary_country_name}" if len(sorted_countries) == 1 
                              else f"Primary country: {primary_country_relay_count} of {total_relay_count} relays in {primary_country_name}",
                    'all_countries': [{'country': code, 'country_name': country_names.get(code, code), 'relay_count': count}
                                    for code, count in sorted_countries]
                }
            else:
                contact_data["primary_country_data"] = None
                
            # Clean up temporary country_counts to save memory
            del contact_data["country_counts"]
            
            # BANDWIDTH MEANS CALCULATION (optimized from _calculate_bandwidth_means)
            relays = contact_data.get("relays", [])
            total_bandwidth = contact_data.get("bandwidth", 0)
            
            if len(relays) > 0:
                # Calculate mean bandwidth
                mean_bandwidth = total_bandwidth / len(relays)
                contact_data["bandwidth_mean"] = mean_bandwidth
                
                # OPTIMIZED: Combined display format following dominant codebase pattern
                unit = self.bandwidth_formatter.determine_unit(mean_bandwidth)
                formatted_mean = self.bandwidth_formatter.format_bandwidth_with_unit(mean_bandwidth, unit)
                contact_data["bandwidth_mean_display"] = f"{formatted_mean} {unit}"
            else:
                # Handle edge case of no relays
                contact_data["bandwidth_mean"] = 0
                fallback_unit = "KB/s" if not self.use_bits else "Kbit/s"
                contact_data["bandwidth_mean_display"] = f"0.00 {fallback_unit}"

    def _precompute_display_values(self):
        """
        PERF: Pre-compute display strings for misc listing pages (30-40% speedup).
        Used by misc-families.html, misc-contacts.html, misc-networks.html, etc.
        """
        fmt = self.bandwidth_formatter  # Alias for brevity
        
        for category in ["family", "contact", "as", "country", "platform", "flag"]:
            if category not in self.json["sorted"]:
                continue
                
            for key, data in self.json["sorted"][category].items():
                # Bandwidth: determine unit once, format all values
                unit = fmt.determine_unit(data.get("bandwidth", 0))
                bw = fmt.format_bandwidth_with_unit(data.get("bandwidth", 0), unit)
                g_bw = fmt.format_bandwidth_with_unit(data.get("guard_bandwidth", 0), unit)
                m_bw = fmt.format_bandwidth_with_unit(data.get("middle_bandwidth", 0), unit)
                e_bw = fmt.format_bandwidth_with_unit(data.get("exit_bandwidth", 0), unit)
                
                # Consensus weight percentages
                cw = data.get("consensus_weight_fraction", 0) * 100
                g_cw = data.get("guard_consensus_weight_fraction", 0) * 100
                m_cw = data.get("middle_consensus_weight_fraction", 0) * 100
                e_cw = data.get("exit_consensus_weight_fraction", 0) * 100
                
                # Relay counts
                g_cnt = data.get("guard_count", 0)
                m_cnt = data.get("middle_count", 0)
                e_cnt = data.get("exit_count", 0)
                
                # First seen date (strip time)
                first_seen = data.get("first_seen", "")
                
                data["display"] = {
                    "bandwidth_unit": unit,
                    "bandwidth_formatted": bw,
                    "guard_bw_formatted": g_bw,
                    "middle_bw_formatted": m_bw,
                    "exit_bw_formatted": e_bw,
                    "bw_combined": f"{bw} / {g_bw} / {m_bw} / {e_bw} {unit}",
                    "cw_overall_pct": f"{cw:.2f}%",
                    "cw_guard_pct": f"{g_cw:.2f}%",
                    "cw_middle_pct": f"{m_cw:.2f}%",
                    "cw_exit_pct": f"{e_cw:.2f}%",
                    "cw_combined": f"{cw:.2f}% / {g_cw:.2f}% / {m_cw:.2f}% / {e_cw:.2f}%",
                    "count_combined": f"{g_cnt} / {m_cnt} / {e_cnt}",
                    "total_relays": len(data.get("relays", [])),
                    "first_seen_date": first_seen.split(" ", 1)[0] if first_seen else "",
                }

    def _precompute_all_contact_page_data(self):
        """
        PERF OPTIMIZATION: Pre-compute all contact page data using parallel processing.
        
        Previously, contact pages were excluded from parallel generation because they
        required expensive per-page calculations. By pre-computing this data during
        the Data Processing phase using multiprocessing, we achieve ~10x speedup
        for contact page generation.
        
        Pre-computes for each contact:
        - contact_rankings: AROI leaderboard rankings
        - operator_reliability: Uptime/bandwidth reliability statistics
        - contact_display_data: Formatted display values
        - contact_validation_status: AROI validation status
        - is_validated_aroi: Whether contact has validated AROI domain
        """
        if "contact" not in self.json["sorted"]:
            return
        
        contact_hashes = list(self.json["sorted"]["contact"].keys())
        if not contact_hashes:
            return
        
        # Pre-compute AROI validation timestamp once (same for all contacts)
        aroi_validation_timestamp = self._get_aroi_validation_timestamp()
        validated_aroi_domains = getattr(self, 'validated_aroi_domains', set())
        
        # Use multiprocessing if available and beneficial
        use_mp = (self.mp_workers > 0 and len(contact_hashes) >= 100 and 
                  hasattr(mp, 'get_context'))
        
        if use_mp:
            try:
                self._precompute_contacts_parallel(contact_hashes, aroi_validation_timestamp, 
                                                   validated_aroi_domains)
                return
            except Exception as e:
                # Fall back to sequential if parallel fails
                if self.progress:
                    self._log_progress(f"Parallel precomputation failed ({e}), using sequential...")
        
        # Sequential fallback
        for contact_hash in contact_hashes:
            self._precompute_single_contact(contact_hash, aroi_validation_timestamp, 
                                            validated_aroi_domains)
    
    def _precompute_single_contact(self, contact_hash, aroi_validation_timestamp, validated_aroi_domains):
        """Precompute data for a single contact (used by both sequential and parallel paths).
        
        Stores precomputed values directly on contact_data for simple access (Sonnet-style).
        """
        contact_data = self.json["sorted"]["contact"][contact_hash]
        
        # Get member relays for this contact
        members = [self.json["relays"][idx] for idx in contact_data.get("relays", [])]
        if not members:
            return
        
        # Determine bandwidth unit for this contact
        bandwidth_unit = self.bandwidth_formatter.determine_unit(contact_data.get("bandwidth", 0))
        
        # Pre-compute contact rankings
        contact_data["contact_rankings"] = self._generate_contact_rankings(contact_hash)
        
        # Pre-compute operator reliability statistics
        contact_data["operator_reliability"] = self._calculate_operator_reliability(contact_hash, members)
        
        # Pre-compute contact display data
        contact_data["contact_display_data"] = self._compute_contact_display_data(
            contact_data, bandwidth_unit, contact_data["operator_reliability"], contact_hash, members
        )
        
        # Pre-compute AROI validation status
        if "aroi_validation_full" in contact_data:
            contact_data["contact_validation_status"] = contact_data["aroi_validation_full"]
        else:
            contact_data["contact_validation_status"] = self._get_contact_validation_status(members)
        
        # Store AROI validation timestamp and is_validated flag
        contact_data["aroi_validation_timestamp"] = aroi_validation_timestamp
        
        # Check if this contact has a validated AROI domain
        aroi_domain = members[0].get("aroi_domain") if members else None
        contact_data["is_validated_aroi"] = (aroi_domain and aroi_domain != "none" and 
                                              aroi_domain in validated_aroi_domains)
        contact_data["aroi_domain"] = aroi_domain  # Store for vanity URL generation
        
        # Store bandwidth unit for template use
        contact_data["precomputed_bandwidth_unit"] = bandwidth_unit
    
    def _precompute_contacts_parallel(self, contact_hashes, aroi_validation_timestamp, validated_aroi_domains):
        """Parallel precomputation using fork() with imap_unordered for better memory and progress.
        
        Uses chunked imap_unordered (GPT-style streaming) instead of map() to:
        - Keep peak memory lower by processing results as they complete
        - Enable granular progress reporting during precomputation
        """
        # Use fork context for efficient memory sharing
        ctx = mp.get_context('fork')
        
        # Prepare arguments for worker function
        worker_args = [(contact_hash, aroi_validation_timestamp, validated_aroi_domains) 
                       for contact_hash in contact_hashes]
        
        total_contacts = len(contact_hashes)
        processed = 0
        chunk_size = max(50, total_contacts // (self.mp_workers * 4))  # Balance granularity vs overhead
        
        # Initialize workers with self reference (fork shares memory)
        with ctx.Pool(self.mp_workers, _init_precompute_worker, (self,)) as pool:
            # Use imap_unordered for streaming results (lower peak memory)
            for contact_hash, precomputed_data in pool.imap_unordered(
                _precompute_contact_worker, worker_args, chunksize=chunk_size
            ):
                # Apply result directly to contact data (flat storage pattern)
                if precomputed_data and contact_hash in self.json["sorted"]["contact"]:
                    contact_data = self.json["sorted"]["contact"][contact_hash]
                    # Store each field directly on contact_data (Sonnet-style simple access)
                    for key, value in precomputed_data.items():
                        contact_data[key] = value
                
                # Progress reporting
                processed += 1
                if processed % 500 == 0:
                    self._log_progress(f"Pre-computed {processed}/{total_contacts} contacts...")

    def _generate_aroi_leaderboards(self):
        """
        Generate AROI operator leaderboards using pre-processed relay data.
        """
        self.json['aroi_leaderboards'] = _calculate_aroi_leaderboards(self)

    def _generate_smart_context(self):
        """
        Generate smart context information using intelligence engine
        """
        try:
            from .intelligence_engine import IntelligenceEngine
        except ImportError as e:
            if self.progress:
                self._log_progress(f"Intelligence engine not available: {e}")
            print("⚠️  Intelligence engine module not available, skipping analysis")
            self.json['smart_context'] = {}
            self.progress_step += 2  # Skip both analysis steps
            return
        
        self.progress_step += 1
        self._log_progress("Starting Tier 1 intelligence analysis...")
        engine = IntelligenceEngine(self.json)
        self.json['smart_context'] = engine.analyze_all_layers()
        self.progress_step += 1
        self._log_progress("Tier 1 intelligence analysis complete")

    def create_output_dir(self):
        """
        Ensure self.output_dir exists (required for write functions)
        """
        os.makedirs(self.output_dir, exist_ok=True)

    def write_misc(
        self,
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
        relay_subset = self.json["relays"]
        
        # Handle page context and path prefix
        if page_ctx is None:
            page_ctx = {'path_prefix': '../'}  # default fallback
        
        # Add AROI validation status to contact data for misc-contacts templates
        # This runs before write_pages_by_key, so we calculate once and store for reuse
        if template.name == "misc-contacts.html":
            for contact_hash, contact_data in self.json["sorted"].get("contact", {}).items():
                # Only calculate if not already stored
                if "aroi_validation_status" not in contact_data:
                    relay_indices = contact_data.get("relays", [])
                    members = [self.json["relays"][idx] for idx in relay_indices]
                    validation_status = self._get_contact_validation_status(members)
                    contact_data["aroi_validation_status"] = validation_status["validation_status"]
                    # Store full validation status for operator pages to reuse
                    contact_data["aroi_validation_full"] = validation_status
        
        # Pre-compute family statistics for misc-families templates
        template_vars = {
            "relays": self,
            "relay_subset": relay_subset,  # Pass directly for thread safety
            "sorted_by": sorted_by,
            "reverse": reverse,
            "is_index": is_index,
            "page_ctx": page_ctx,
            "validated_aroi_domains": self.validated_aroi_domains if hasattr(self, 'validated_aroi_domains') else set(),
            "base_url": self.base_url,
        }
        
        if template.name == "misc-families.html":
            family_stats = self.json.get('family_statistics', {
                'centralization_percentage': '0.0',
                'largest_family_size': 0,
                'large_family_count': 0
            })
            template_vars.update(family_stats)
        elif template.name == "misc-authorities.html":
            # Reuse existing authority uptime data from consolidated processing
            authorities_data = self._get_directory_authorities_data()
            # Set attributes as expected by template (template uses relays.X)
            self.authorities_data = authorities_data['authorities_data']
            self.authorities_summary = authorities_data['authorities_summary']
            self.consensus_status = authorities_data.get('consensus_status')
            self.latency_summary = authorities_data.get('latency_summary')
            self.authority_alerts = authorities_data.get('authority_alerts')
            self.collector_flag_thresholds = authorities_data.get('collector_flag_thresholds')
            self.collector_fetched_at = authorities_data.get('collector_fetched_at')
            template_vars.update(authorities_data)
        
        template_render = template.render(**template_vars)
        output = os.path.join(self.output_dir, path)
        os.makedirs(os.path.dirname(output), exist_ok=True)

        with open(output, "w", encoding="utf8") as html:
            html.write(template_render)

    def _get_directory_authorities_data(self):
        """
        Prepare directory authorities data for template rendering.
        Reuses existing authority uptime calculations and z-score infrastructure.
        """
        from datetime import datetime, timezone
        
        # Filter authorities from existing relay data (no new processing)
        authorities = [relay for relay in self.json["relays"] if 'Authority' in relay.get('flags', [])]
        
        # Sort authorities alphabetically by nickname (A at top, Z at bottom)
        authorities = sorted(authorities, key=lambda x: x.get('nickname', '').lower())
        
        # Get collector data for votes/bw authorities
        collector_data = getattr(self, 'collector_consensus_data', None)
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
        
        if hasattr(self, '_consolidated_uptime_results'):
            network_flag_stats = self._consolidated_uptime_results.get('network_flag_statistics', {})
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
        collector_flag_thresholds = getattr(self, 'collector_flag_thresholds', None)
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
            'uptime_metadata': (getattr(self, 'uptime_data', {}) or {}).get('relays_published', 'Unknown'),
            'consensus_status': consensus_status,
            'latency_summary': latency_summary,
            'authority_alerts': authority_alerts if authority_alerts else None,
            'collector_flag_thresholds': collector_flag_thresholds,
            'collector_fetched_at': collector_fetched_at,
        }



    def _format_time_ago(self, timestamp_str):
        """Format timestamp as multi-unit time ago (e.g., '2y 3m 2w ago')"""
        # Use the module-level function to avoid code duplication
        return format_time_ago(timestamp_str)

    def get_detail_page_context(self, category, value):
        """Generate page context with correct breadcrumb data for detail pages"""
        # Use centralized page context generation
        from .page_context import get_detail_page_context
        return get_detail_page_context(category, value)

    def write_pages_by_key(self, k):
        """Render and write sorted HTML relay listings to disk"""
        start_time = time.time()
        self._log_progress(f"Starting {k} page generation...")
        
        template = ENV.get_template(k + ".html")
        output_path = os.path.join(self.output_dir, k)

        the_prefixed = [
            "Dominican Republic", "Ivory Coast", "Marshall Islands",
            "Northern Marianas Islands", "Solomon Islands", "United Arab Emirates",
            "United Kingdom", "United States", "United States of America",
            "Vatican City", "Czech Republic", "Bahamas", "Gambia", "Netherlands",
            "Philippines", "Seychelles", "Sudan", "Ukraine",
        ]

        if os.path.exists(output_path):
            rmtree(output_path)

        sorted_values = sorted(self.json["sorted"][k].keys()) if k == "first_seen" else list(self.json["sorted"][k].keys())
        
        # Use multiprocessing for large page sets on systems with fork()
        # Contact pages now use precomputed data so they can be parallelized too
        use_mp = (self.mp_workers > 0 and len(sorted_values) >= 100 and 
                  hasattr(mp, 'get_context'))
        
        if use_mp:
            self._write_pages_parallel(k, sorted_values, template, output_path, the_prefixed, start_time)
            return
        
        page_count = render_time = io_time = 0
        
        for v in sorted_values:
            # Sanitize the value to prevent directory traversal attacks
            v = v.replace("..", "").replace("/", "_")
            i = self.json["sorted"][k][v]
            members = []

            for m_relay in i["relays"]:
                members.append(self.json["relays"][m_relay])
            if k == "flag":
                dir_path = os.path.join(output_path, v.lower())
            else:
                dir_path = os.path.join(output_path, v)

            os.makedirs(dir_path)
            # relay_subset passed directly to template for thread safety (no shared state)
            
            bandwidth_unit = self.bandwidth_formatter.determine_unit(i["bandwidth"])
            # Format all bandwidth values using the same unit
            bandwidth = self.bandwidth_formatter.format_bandwidth_with_unit(i["bandwidth"], bandwidth_unit)
            guard_bandwidth = self.bandwidth_formatter.format_bandwidth_with_unit(i["guard_bandwidth"], bandwidth_unit)
            middle_bandwidth = self.bandwidth_formatter.format_bandwidth_with_unit(i["middle_bandwidth"], bandwidth_unit)
            exit_bandwidth = self.bandwidth_formatter.format_bandwidth_with_unit(i["exit_bandwidth"], bandwidth_unit)
            
            # Calculate network position using intelligence engine
            try:
                from .intelligence_engine import IntelligenceEngine
                intelligence = IntelligenceEngine({})  # Empty intelligence engine just for utility method
                total_relays = len(members)
                network_position = intelligence._calculate_network_position(
                    i["guard_count"], i["middle_count"], i["exit_count"], total_relays
                )
                # Use the pre-formatted string from intelligence engine
                network_position_display = network_position.get('formatted_string', 'unknown')
            except ImportError:
                # Fallback if intelligence engine is not available
                total_relays = len(members)
                guard_ratio = i["guard_count"] / total_relays if total_relays > 0 else 0
                middle_ratio = i["middle_count"] / total_relays if total_relays > 0 else 0
                exit_ratio = i["exit_count"] / total_relays if total_relays > 0 else 0
                
                # Simple network position calculation
                if guard_ratio > 0.5:
                    network_position_label = "Guard-focused"
                elif exit_ratio > 0.5:
                    network_position_label = "Exit-focused"
                elif middle_ratio > 0.5:
                    network_position_label = "Middle-focused"
                else:
                    network_position_label = "Mixed"
                
                # Create simple fallback display
                position_components = []
                if i["guard_count"] > 0:
                    guard_text = 'guard' if i["guard_count"] == 1 else 'guards'
                    position_components.append(f"{i['guard_count']} {guard_text}")
                if i["middle_count"] > 0:
                    middle_text = 'middle' if i["middle_count"] == 1 else 'middles'
                    position_components.append(f"{i['middle_count']} {middle_text}")
                if i["exit_count"] > 0:
                    exit_text = 'exit' if i["exit_count"] == 1 else 'exits'
                    position_components.append(f"{i['exit_count']} {exit_text}")
                
                total_text = 'relay' if total_relays == 1 else 'relays'
                components_text = ', ' + ', '.join(position_components) if position_components else ''
                network_position_display = f"{network_position_label} ({total_relays} total {total_text}{components_text})"
                
                # Create fallback network_position object
                network_position = {
                    'label': network_position_label,
                    'formatted_string': network_position_display
                }
                
            except Exception as e:
                print(f"DEBUG: Network position calculation error for {k}={v}: {e}")
                network_position = {
                    'label': 'error',
                    'formatted_string': f'calculation error: {str(e)}'
                }
            
            # Generate page context with correct breadcrumb data
            page_ctx = self.get_detail_page_context(k, v)
            
            # Generate contact rankings for AROI leaderboards (only for contact pages)
            contact_rankings = []
            operator_reliability = None
            contact_display_data = None
            primary_country_data = None
            contact_validation_status = None
            aroi_validation_timestamp = None
            if k == "contact":
                contact_rankings = self._generate_contact_rankings(v)
                # Calculate operator reliability statistics
                operator_reliability = self._calculate_operator_reliability(v, members)
                # Pre-compute all contact-specific display data
                contact_display_data = self._compute_contact_display_data(
                    i, bandwidth_unit, operator_reliability, v, members
                )
                # Store contact_display_data in the contact structure for relay pages to access
                i['contact_display_data'] = contact_display_data
                # Get primary country data for this contact
                primary_country_data = i.get("primary_country_data")
                # Get AROI validation status for this contact (Phase 2)
                # Reuse validation status from write_misc if already calculated, otherwise calculate now
                if "aroi_validation_full" in i:
                    contact_validation_status = i["aroi_validation_full"]
                else:
                    contact_validation_status = self._get_contact_validation_status(members)
                # Extract AROI validation timestamp for display
                aroi_validation_timestamp = self._get_aroi_validation_timestamp()
            
            # Add family-specific data for family templates (used by detail_summary macro)
            family_aroi_domain = None
            family_contact = None
            family_contact_md5 = None
            if k == "family":
                family_aroi_domain = i.get("aroi_domain", "")
                family_contact = i.get("contact", "")
                family_contact_md5 = i.get("contact_md5", "")
            
            # Check if this contact has a validated AROI domain for vanity URL display
            is_validated_aroi = False
            if k == "contact" and members and hasattr(self, 'validated_aroi_domains'):
                aroi_domain = members[0].get("aroi_domain")
                is_validated_aroi = aroi_domain and aroi_domain != "none" and aroi_domain in self.validated_aroi_domains
            
            # Time the template rendering
            render_start = time.time()
            rendered = template.render(
                relays=self,
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
                validated_aroi_domains=self.validated_aroi_domains if hasattr(self, 'validated_aroi_domains') else set(),
                # Base URL for vanity URLs
                base_url=self.base_url
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
            if self.base_url and k == "contact" and members and hasattr(self, 'validated_aroi_domains'):
                aroi_domain = members[0].get("aroi_domain")
                if aroi_domain and aroi_domain != "none" and aroi_domain in self.validated_aroi_domains:
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
                self._log_progress(f"Processed {page_count} {k} pages...")

        end_time = time.time()
        total_time = end_time - start_time
        
        # Log completion with progress increment for granular tracking
        self.progress_logger.log(f"{k} page generation complete - Generated {page_count} pages in {total_time:.2f}s")
        if self.progress:
            # Additional detailed stats (not in standard format, but supporting info)
            print(f"    🎨 Template render time: {render_time:.2f}s ({render_time/total_time*100:.1f}%)")
            print(f"    💾 File I/O time: {io_time:.2f}s ({io_time/total_time*100:.1f}%)")
            if page_count > 0:
                print(f"    ⚡ Average per page: {total_time/page_count*1000:.1f}ms")
            print("---")

    def _build_template_args(self, k, v, i, the_prefixed, validated_aroi_domains):
        """Build template arguments for all page types (used by both sequential and parallel paths)."""
        members = [self.json["relays"][idx] for idx in i["relays"]]
        bw = self.bandwidth_formatter
        bw_unit = bw.determine_unit(i["bandwidth"])
        
        # Calculate network position
        try:
            from .intelligence_engine import IntelligenceEngine
            network_position = IntelligenceEngine({})._calculate_network_position(
                i["guard_count"], i["middle_count"], i["exit_count"], len(members))
        except Exception:
            network_position = {'label': 'Mixed', 'formatted_string': f'{len(members)} relays'}
        
        # For contact pages, use precomputed data stored directly on contact_data
        # (flat storage pattern for simpler access - Sonnet-style with Opus-style parallel precompute)
        if k == "contact":
            contact_rankings = i.get("contact_rankings", [])
            operator_reliability = i.get("operator_reliability")
            contact_display_data = i.get("contact_display_data")
            contact_validation_status = i.get("contact_validation_status")
            aroi_validation_timestamp = i.get("aroi_validation_timestamp")
            is_validated_aroi = i.get("is_validated_aroi", False)
            primary_country_data = i.get("primary_country_data")
        else:
            contact_rankings = []
            operator_reliability = None
            contact_display_data = None
            contact_validation_status = None
            aroi_validation_timestamp = None
            is_validated_aroi = False
            primary_country_data = None
        
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
            'page_ctx': self.get_detail_page_context(k, v),
            'key': k, 'value': v,
            'flag': v if k == "flag" else None,
            'sp_countries': the_prefixed,
            'contact_rankings': contact_rankings,
            'operator_reliability': operator_reliability,
            'contact_display_data': contact_display_data,
            'primary_country_data': primary_country_data,
            'contact_validation_status': contact_validation_status,
            'aroi_validation_timestamp': aroi_validation_timestamp,
            'family_aroi_domain': i.get("aroi_domain", "") if k == "family" else None,
            'family_contact': i.get("contact", "") if k == "family" else None,
            'family_contact_md5': i.get("contact_md5", "") if k == "family" else None,
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
            'base_url': self.base_url,
        }

    def _write_pages_parallel(self, k, sorted_values, template, output_path, the_prefixed, start_time):
        """Parallel page generation using fork() for ~70% speedup on large page sets."""
        validated_aroi_domains = getattr(self, 'validated_aroi_domains', set())
        page_args = []
        vanity_url_tasks = []  # Collect vanity URL tasks for post-processing
        
        for v in sorted_values:
            v = v.replace("..", "").replace("/", "_")
            i = self.json["sorted"][k][v]
            dir_path = os.path.join(output_path, v.lower() if k == "flag" else v)
            os.makedirs(dir_path, exist_ok=True)
            html_path = os.path.join(dir_path, "index.html")
            page_args.append((html_path, self._build_template_args(k, v, i, the_prefixed, validated_aroi_domains)))
            
            # Collect vanity URL tasks for contact pages (to be processed after parallel generation)
            # Uses precomputed aroi_domain to avoid re-fetching members
            if k == "contact" and self.base_url and i.get("is_validated_aroi"):
                aroi_domain = i.get("aroi_domain")
                if aroi_domain and aroi_domain != "none":
                    vanity_url_tasks.append((html_path, aroi_domain, output_path))
        
        try:
            ctx = mp.get_context('fork')
            with ctx.Pool(self.mp_workers, _init_mp_worker, (self, template)) as pool:
                pool.map(_render_page_mp, page_args)
            
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
            self.progress_logger.log(f"{k} page generation complete - Generated {len(page_args)} pages in {total_time:.2f}s")
            if self.progress:
                print(f"    🚀 Parallel: {self.mp_workers} workers, {total_time/len(page_args)*1000:.1f}ms/page avg")
        except Exception as e:
            self._log_progress(f"Multiprocessing failed ({e}), falling back to sequential...")
            self.mp_workers = 0
            self.write_pages_by_key(k)

    def write_relay_info(self):
        """
        Render and write per-relay HTML info documents to disk
        """
        relay_list = self.json["relays"]
        template = ENV.get_template("relay-info.html")
        output_path = os.path.join(self.output_dir, "relay")

        if os.path.exists(output_path):
            rmtree(output_path)
        os.makedirs(output_path)

        for relay in relay_list:
            if not relay["fingerprint"].isalnum():
                continue
            # Use centralized page context generation
            from .page_context import StandardTemplateContexts
            
            # Get the contact display data from existing contact structure
            contact_display_data = self._get_contact_display_data_for_relay(relay)
            
            standard_contexts = StandardTemplateContexts(self)
            full_context = standard_contexts.get_relay_page_context(relay, contact_display_data)
            page_ctx = full_context
            
            rendered = template.render(
                relay=relay, page_ctx=page_ctx, relays=self, contact_display_data=contact_display_data,
                validated_aroi_domains=self.validated_aroi_domains if hasattr(self, 'validated_aroi_domains') else set(),
                base_url=self.base_url
            )
            
            # Create directory structure: relay/FINGERPRINT/index.html (depth 2)
            relay_dir = os.path.join(output_path, relay["fingerprint"])
            os.makedirs(relay_dir)
            
            with open(
                os.path.join(relay_dir, "index.html"),
                "w",
                encoding="utf8",
            ) as html:
                html.write(rendered)

    def _get_contact_display_data_for_relay(self, relay):
        """
        Get existing contact display data for a relay by looking up its contact hash.
        
        Args:
            relay (dict): Single relay object
            
        Returns:
            dict: Contact display data if available, empty dict otherwise
        """
        contact_hash = relay.get('contact_md5')
        if not contact_hash:
            return {}
        
        # Check if this contact has already computed display data in sorted contacts
        contact_data = self.json.get("sorted", {}).get("contact", {}).get(contact_hash)
        if not contact_data:
            return {}
        
        # If contact display data was already computed and stored, return it
        if 'contact_display_data' in contact_data:
            return contact_data['contact_display_data']
        
        # Otherwise return empty dict and template will use fallback
        return {}

    def _get_contact_validation_status(self, members):
        """
        Get AROI validation status for a contact's relays (Phase 2).
        
        Args:
            members (list): List of relay objects for this contact
            
        Returns:
            dict: Validation status information from get_contact_validation_status
        """
        from .aroi_validation import get_contact_validation_status
        
        # Get the validation data and pre-built validation_map
        validation_data = getattr(self, 'aroi_validation_data', None)
        validation_map = getattr(self, 'validation_map', None)
        
        # Pass shared validation_map to avoid rebuilding it 3,000+ times
        return get_contact_validation_status(members, validation_data, validation_map)
    
    def _get_aroi_validation_timestamp(self):
        """
        Get formatted timestamp from AROI validation data.
        
        Returns:
            str: Formatted timestamp or 'Unknown' if not available
        """
        from .aroi_validation import _format_timestamp
        
        validation_data = getattr(self, 'aroi_validation_data', None)
        if not validation_data:
            return 'Unknown'
        
        metadata = validation_data.get('metadata', {})
        timestamp_str = metadata.get('timestamp', '')
        
        return _format_timestamp(timestamp_str)

    def _generate_contact_rankings(self, contact_hash):
        """
        Generate AROI leaderboard rankings for a specific contact hash.
        Returns list of ranking achievements for display on contact pages.
        """
        if not hasattr(self, 'json') or not self.json.get('aroi_leaderboards'):
            return []
        
        leaderboards = self.json['aroi_leaderboards'].get('leaderboards', {})
        rankings = []
        
        # Check each leaderboard category for this contact
        for category, leaders in leaderboards.items():
            for rank, entry in enumerate(leaders, 1):
                # Handle both formatted entries (dict) and raw tuples
                if isinstance(entry, dict):
                    leader_contact = entry.get('contact_hash')
                else:
                    # Handle tuple format (leader_contact, data)
                    leader_contact, data = entry
                
                if leader_contact == contact_hash:
                    # Only show top 25 rankings
                    if rank <= 25:
                        category_info = self._get_leaderboard_category_info(category)
                        rankings.append({
                            'category': category,
                            'category_name': category_info['name'],
                            'rank': rank,
                            'emoji': category_info['emoji'],
                            'title': category_info['title'],
                            'statement': f"#{rank} {category_info['name']}",
                            'link': f"aroi-leaderboards.html#{category}"
                        })
                    break
        
        # Sort rankings by rank (1st place first, 25th place last)
        rankings.sort(key=lambda x: x['rank'])
        
        return rankings

    def _get_leaderboard_category_info(self, category):
        """
        Get display information for a leaderboard category.
        
        Args:
            category (str): Category key
            
        Returns:
            dict: Category display information
        """
        # DRY helper function: when name and title are identical
        def _info(name, emoji):
            return {'name': name, 'emoji': emoji, 'title': name}
        
        category_info = {
            'bandwidth': _info('Bandwidth Capacity Champion', '🚀'),
            'consensus_weight': _info('Network Heavyweight', '⚖️'),
            'exit_authority': _info('Exit Heavyweight Master', '🚪'),
            'guard_authority': _info('Guard Heavyweight Master', '🛡️'),
            'exit_operators': _info('Exit Champion', '🚪'),
            'guard_operators': _info('Guard Gatekeepers', '🛡️'),
            'most_diverse': _info('Diversity Master', '🌈'),
            'platform_diversity': _info('Platform Hero', '💻'),
            'non_eu_leaders': _info('Non-EU Leader', '🌍'),
            'frontier_builders': _info('Frontier Builder', '🏴‍☠️'),
            'network_veterans': _info('Network Veteran', '🏆'),
            'reliability_masters': _info('Reliability Master', '⏰'),
            'legacy_titans': _info('Legacy Titan', '👑'),
            'ipv4_leaders': _info('IPv4 Address Leaders', '🌐'),
            'ipv6_leaders': _info('IPv6 Address Leaders', '🔮')
        }
        
        # Default for unknown categories
        default_name = category.replace('_', ' ').title()
        return category_info.get(category, _info(default_name, '🏅'))

    def _calculate_operator_reliability(self, contact_hash, operator_relays):
        """
        Calculate comprehensive reliability statistics for an operator.
        
        Uses shared uptime utilities to avoid code duplication with aroileaders.py.
        Uses cached network percentiles for efficiency (calculated once in _reprocess_uptime_data).
        
        NEW: Also calculates bandwidth reliability metrics using shared bandwidth utilities.
        
        Args:
            contact_hash (str): Contact hash for the operator
            operator_relays (list): List of relay objects for this operator
            
        Returns:
            dict: Reliability statistics including overall uptime, time periods, outliers, network percentiles,
                  and bandwidth performance metrics
        """
        uptime_data = getattr(self, 'uptime_data', None)
        bandwidth_data = getattr(self, 'bandwidth_data', None)
        if (not uptime_data and not bandwidth_data) or not operator_relays:
            return None
            
        from .uptime_utils import (
            extract_relay_uptime_for_period, 
            calculate_statistical_outliers,
            find_operator_percentile_position
        )
        from .bandwidth_utils import extract_relay_bandwidth_for_period, extract_operator_daily_bandwidth_totals
        import statistics
        
        # Available time periods from Onionoo APIs
        uptime_periods = ['1_month', '3_months', '6_months', '1_year', '5_years']
        bandwidth_periods = ['6_months', '1_year', '5_years']  # Bandwidth has different available periods
        period_display_names = {
            '1_month': '30d',
            '3_months': '90d', 
            '6_months': '6mo',
            '1_year': '1y',
            '5_years': '5y'
        }
        
        reliability_stats = {
            # === UPTIME METRICS (existing) ===
            'overall_uptime': {},  # Unweighted average uptime per time period
            'relay_uptimes': [],   # Individual relay uptime data
            'outliers': {          # Statistical outliers (2+ std dev from mean)
                'low_outliers': [],
                'high_outliers': []
            },
            'network_uptime_percentiles': None,  # Network-wide percentiles for 6-month period
            
            # === BANDWIDTH METRICS (new) ===
            'overall_bandwidth': {},  # Average bandwidth per time period
            'relay_bandwidths': [],   # Individual relay bandwidth data
            'bandwidth_outliers': {   # Bandwidth statistical outliers
                'low_outliers': [],
                'high_outliers': []
            },
            'network_bandwidth_percentiles': None,  # Network-wide bandwidth percentiles for 6-month period
            'operator_daily_bandwidth': {},  # Daily total bandwidth averages per period
            
            # === COMMON METRICS ===
            'valid_relays': 0,
            'total_relays': len(operator_relays)
        }
        
        # PERFORMANCE OPTIMIZATION: Use cached network percentiles instead of recalculating
        # Network percentiles are calculated once in _reprocess_uptime_data for all contacts
        if hasattr(self, 'network_uptime_percentiles') and self.network_uptime_percentiles:
            reliability_stats['network_uptime_percentiles'] = self.network_uptime_percentiles
            
        # BANDWIDTH PERCENTILES: Use cached bandwidth percentiles if available
        if hasattr(self, 'network_bandwidth_percentiles') and self.network_bandwidth_percentiles:
            reliability_stats['network_bandwidth_percentiles'] = self.network_bandwidth_percentiles
        
        # Process uptime data for each time period using shared utilities
        all_relay_data = {}
        
        if uptime_data:
            for period in uptime_periods:
                # Extract uptime data for this period using shared utility
                period_result = extract_relay_uptime_for_period(operator_relays, uptime_data, period)
            
                if period_result['uptime_values']:
                    mean_uptime = statistics.mean(period_result['uptime_values'])
                    std_dev = statistics.stdev(period_result['uptime_values']) if len(period_result['uptime_values']) > 1 else 0
                    
                    reliability_stats['overall_uptime'][period] = {
                        'average': mean_uptime,
                        'std_dev': std_dev,
                        'display_name': period_display_names[period],
                        'relay_count': len(period_result['uptime_values'])
                    }
                    
                    # For 6-month period, add network percentile comparison using cached data
                    if period == '6_months' and reliability_stats['network_uptime_percentiles']:
                        operator_position_info = find_operator_percentile_position(mean_uptime, reliability_stats['network_uptime_percentiles'])
                        reliability_stats['overall_uptime'][period]['network_position'] = operator_position_info['description']
                        reliability_stats['overall_uptime'][period]['percentile_range'] = operator_position_info['percentile_range']
                    
                    # Calculate statistical outliers using shared utility
                    outliers = calculate_statistical_outliers(
                        period_result['uptime_values'], 
                        period_result['relay_breakdown']
                    )
                    
                    # Add period information to outliers
                    for outlier in outliers['low_outliers']:
                        outlier['period'] = period
                    for outlier in outliers['high_outliers']:
                        outlier['period'] = period
                    
                    # Collect outliers from all periods
                    reliability_stats['outliers']['low_outliers'].extend(outliers['low_outliers'])
                    reliability_stats['outliers']['high_outliers'].extend(outliers['high_outliers'])
                    
                    # Collect relay data for relay_uptimes
                    for fingerprint, relay_data in period_result['relay_breakdown'].items():
                        if fingerprint not in all_relay_data:
                            all_relay_data[fingerprint] = {
                                'fingerprint': fingerprint,
                                'nickname': relay_data['nickname'],
                                'uptime_periods': {},
                                'bandwidth_periods': {}  # Add bandwidth support
                            }
                        all_relay_data[fingerprint]['uptime_periods'][period] = relay_data['uptime']
        
        # Process bandwidth data for each time period using shared utilities
        all_bandwidth_relay_data = {}
        
        if bandwidth_data:
            # BANDWIDTH OUTLIERS: Only calculate for 6mo (actionable timeframe)
            # Historical outliers (1y, 5y) are not actionable for current operations
            bandwidth_outlier_periods = ['6_months']  # Only current/recent outliers are actionable
            
            for period in bandwidth_periods:
                # Extract individual relay bandwidth data for this period
                period_result = extract_relay_bandwidth_for_period(operator_relays, bandwidth_data, period)
                
                if period_result['bandwidth_values']:
                    mean_bandwidth = statistics.mean(period_result['bandwidth_values'])
                    std_dev = statistics.stdev(period_result['bandwidth_values']) if len(period_result['bandwidth_values']) > 1 else 0
                    
                    # Format bandwidth with appropriate units for display
                    unit = self.bandwidth_formatter.determine_unit(mean_bandwidth)
                    formatted_bandwidth = self.bandwidth_formatter.format_bandwidth_with_unit(mean_bandwidth, unit)
                    
                    reliability_stats['overall_bandwidth'][period] = {
                        'average': mean_bandwidth,
                        'average_formatted': f"{formatted_bandwidth} {unit}",
                        'std_dev': std_dev,
                        'display_name': period_display_names[period],
                        'relay_count': len(period_result['bandwidth_values'])
                    }
                    
                    # PROPOSAL METRICS: Calculate advanced bandwidth reliability metrics
                    from .bandwidth_utils import calculate_bandwidth_reliability_metrics
                    advanced_metrics = calculate_bandwidth_reliability_metrics(
                        operator_relays, bandwidth_data, period, mean_bandwidth, std_dev, 
                        bandwidth_formatter=self.bandwidth_formatter
                    )
                    
                    # Add advanced metrics to the period data
                    reliability_stats['overall_bandwidth'][period].update({
                        'bandwidth_stability': advanced_metrics['bandwidth_stability'],
                        'peak_performance': advanced_metrics['peak_performance'],
                        'growth_trend': advanced_metrics['growth_trend'],
                        'capacity_utilization': advanced_metrics['capacity_utilization']
                    })
                    
                    # For 6-month period, add network percentile comparison using cached data
                    if period == '6_months' and reliability_stats['network_bandwidth_percentiles']:
                        # Create a simple position finder for bandwidth (simpler than uptime version)
                        percentiles = reliability_stats['network_bandwidth_percentiles']
                        if mean_bandwidth >= percentiles['percentile_95']:
                            position_desc = "Top 5%"
                            percentile_range = "95th-100th percentile"
                        elif mean_bandwidth >= percentiles['percentile_75']:
                            position_desc = "Top 25%"
                            percentile_range = "75th-95th percentile"
                        elif mean_bandwidth >= percentiles['percentile_50']:
                            position_desc = "Top 50%"
                            percentile_range = "50th-75th percentile"
                        elif mean_bandwidth >= percentiles['percentile_25']:
                            position_desc = "Top 75%"
                            percentile_range = "25th-50th percentile"
                        else:
                            position_desc = "Bottom 25%"
                            percentile_range = "0-25th percentile"
                            
                        reliability_stats['overall_bandwidth'][period]['network_position'] = position_desc
                        reliability_stats['overall_bandwidth'][period]['percentile_range'] = percentile_range
                    
                    # Calculate bandwidth outliers ONLY for actionable periods (6mo)
                    if period in bandwidth_outlier_periods:
                        # Fix: Convert bandwidth relay_breakdown to use 'value' key expected by statistical utilities
                        bandwidth_relay_breakdown_fixed = {}
                        for fingerprint, relay_data in period_result['relay_breakdown'].items():
                            bandwidth_relay_breakdown_fixed[fingerprint] = relay_data.copy()
                            bandwidth_relay_breakdown_fixed[fingerprint]['value'] = relay_data['bandwidth']
                        
                        bandwidth_outliers = calculate_statistical_outliers(
                            period_result['bandwidth_values'], 
                            bandwidth_relay_breakdown_fixed
                        )
                        
                        # Add period information to bandwidth outliers
                        for outlier in bandwidth_outliers['low_outliers']:
                            outlier['period'] = period
                            # Add formatted bandwidth for display (outlier now has 'value' key)
                            bw_value = outlier.get('value', outlier.get('bandwidth', 0))
                            bw_unit = self.bandwidth_formatter.determine_unit(bw_value)
                            bw_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(bw_value, bw_unit)
                            outlier['value_formatted'] = f"{bw_formatted} {bw_unit}"
                        for outlier in bandwidth_outliers['high_outliers']:
                            outlier['period'] = period
                            # Add formatted bandwidth for display (outlier now has 'value' key)
                            bw_value = outlier.get('value', outlier.get('bandwidth', 0))
                            bw_unit = self.bandwidth_formatter.determine_unit(bw_value)
                            bw_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(bw_value, bw_unit)
                            outlier['value_formatted'] = f"{bw_formatted} {bw_unit}"
                        
                        # Collect bandwidth outliers from actionable periods only
                        reliability_stats['bandwidth_outliers']['low_outliers'].extend(bandwidth_outliers['low_outliers'])
                        reliability_stats['bandwidth_outliers']['high_outliers'].extend(bandwidth_outliers['high_outliers'])
                    
                    # Collect relay bandwidth data for relay_bandwidths
                    for fingerprint, relay_data in period_result['relay_breakdown'].items():
                        if fingerprint not in all_bandwidth_relay_data:
                            all_bandwidth_relay_data[fingerprint] = {
                                'fingerprint': fingerprint,
                                'nickname': relay_data['nickname'],
                                'bandwidth_periods': {}
                            }
                        all_bandwidth_relay_data[fingerprint]['bandwidth_periods'][period] = {
                            'bandwidth': relay_data['bandwidth'],
                            'bandwidth_formatted': self.bandwidth_formatter.format_bandwidth_with_unit(
                                relay_data['bandwidth'],
                                self.bandwidth_formatter.determine_unit(relay_data['bandwidth'])
                            ) + " " + self.bandwidth_formatter.determine_unit(relay_data['bandwidth'])
                        }
                        
                        # Also add to the main relay data if it exists
                        if fingerprint in all_relay_data:
                            all_relay_data[fingerprint]['bandwidth_periods'][period] = relay_data['bandwidth']
            
            # Calculate daily total bandwidth averages for this operator using existing logic
            for period in bandwidth_periods:
                daily_totals_result = extract_operator_daily_bandwidth_totals(operator_relays, bandwidth_data, period)
                if daily_totals_result['daily_totals']:
                    avg_daily_total = daily_totals_result['average_daily_total']
                    
                    # Format for display
                    unit = self.bandwidth_formatter.determine_unit(avg_daily_total)
                    formatted_total = self.bandwidth_formatter.format_bandwidth_with_unit(avg_daily_total, unit)
                    
                    reliability_stats['operator_daily_bandwidth'][period] = {
                        'average_daily_total': avg_daily_total,
                        'average_daily_total_formatted': f"{formatted_total} {unit}",
                        'valid_days': daily_totals_result['valid_days'],
                        'display_name': period_display_names[period]
                    }
        
        # Set relay uptimes and valid relays count
        reliability_stats['relay_uptimes'] = list(all_relay_data.values())
        reliability_stats['valid_relays'] = len(all_relay_data)
        
        # Set relay bandwidth data
        reliability_stats['relay_bandwidths'] = list(all_bandwidth_relay_data.values())
        
        # Remove duplicate outliers (same relay appearing in multiple periods)
        # Keep the one with highest deviation
        def deduplicate_outliers(outliers):
            relay_outliers = {}
            for outlier in outliers:
                fp = outlier['fingerprint']
                if fp not in relay_outliers or outlier['deviation'] > relay_outliers[fp]['deviation']:
                    relay_outliers[fp] = outlier
            return list(relay_outliers.values())
        
        # Deduplicate uptime outliers
        reliability_stats['outliers']['low_outliers'] = deduplicate_outliers(reliability_stats['outliers']['low_outliers'])
        reliability_stats['outliers']['high_outliers'] = deduplicate_outliers(reliability_stats['outliers']['high_outliers'])
        
        # Deduplicate bandwidth outliers
        reliability_stats['bandwidth_outliers']['low_outliers'] = deduplicate_outliers(reliability_stats['bandwidth_outliers']['low_outliers'])
        reliability_stats['bandwidth_outliers']['high_outliers'] = deduplicate_outliers(reliability_stats['bandwidth_outliers']['high_outliers'])
        
        return reliability_stats

    def _format_intelligence_rating(self, rating_text):
        """
        Helper function to format intelligence ratings with color coding.
        
        Args:
            rating_text (str): Rating text like "Poor, 1 network" or "Great, 4 networks"
            
        Returns:
            str: HTML formatted string with color-coded rating
        """
        if not rating_text or ', ' not in rating_text:
            return rating_text
        
        rating, details = rating_text.split(', ', 1)
        
        if 'Poor' in rating:
            return f'<span style="color: #c82333; font-weight: bold;">Poor</span>, {details}'
        elif 'Okay' in rating:
            return f'<span style="color: #cc9900; font-weight: bold;">Okay</span>, {details}'
        else:  # Great or other
            return f'<span style="color: #2e7d2e; font-weight: bold;">Great</span>, {details}'

    def _compute_contact_display_data(self, i, bandwidth_unit, operator_reliability, v, members):
        """
        Compute contact-specific display data for contact pages.
        
        Args:
            i: The relay data for the contact
            bandwidth_unit: The bandwidth unit for the contact
            operator_reliability: The reliability statistics for the contact
            v: The contact hash
            members: The list of relay objects for the contact
            
        Returns:
            dict: Contact-specific display data
        """
        display_data = {}
        
        # 1. Bandwidth components filtering (reuse existing formatting functions)
        bw_components = []
        if i["guard_count"] > 0 and i["guard_bandwidth"] > 0:
            guard_bw = self.bandwidth_formatter.format_bandwidth_with_unit(i["guard_bandwidth"], bandwidth_unit)
            if guard_bw != '0.00':
                bw_components.append(f"{guard_bw} {bandwidth_unit} guard")
        
        if i["middle_count"] > 0 and i["middle_bandwidth"] > 0:
            middle_bw = self.bandwidth_formatter.format_bandwidth_with_unit(i["middle_bandwidth"], bandwidth_unit)
            if middle_bw != '0.00':
                bw_components.append(f"{middle_bw} {bandwidth_unit} middle")
        
        if i["exit_count"] > 0 and i["exit_bandwidth"] > 0:
            exit_bw = self.bandwidth_formatter.format_bandwidth_with_unit(i["exit_bandwidth"], bandwidth_unit)
            if exit_bw != '0.00':
                bw_components.append(f"{exit_bw} {bandwidth_unit} exit")
        
        display_data['bandwidth_breakdown'] = ', '.join(bw_components) if bw_components else None
        
        # 2. Network influence components filtering
        cw_components = []
        if i["guard_count"] > 0 and i["guard_consensus_weight_fraction"] > 0:
            cw_components.append(f"{i['guard_consensus_weight_fraction'] * 100:.2f}% guard")
        
        if i["middle_count"] > 0 and i["middle_consensus_weight_fraction"] > 0:
            cw_components.append(f"{i['middle_consensus_weight_fraction'] * 100:.2f}% middle")
        
        if i["exit_count"] > 0 and i["exit_consensus_weight_fraction"] > 0:
            cw_components.append(f"{i['exit_consensus_weight_fraction'] * 100:.2f}% exit")
        
        display_data['consensus_weight_breakdown'] = ', '.join(cw_components) if cw_components else None
        
        # 3. Operator intelligence formatting (reuse existing contact intelligence data)
        intelligence_formatted = {}
        if hasattr(self, 'json') and self.json.get('smart_context'):
            contact_intel_data = self.json['smart_context'].get('contact_intelligence', {}).get('template_optimized', {})
            contact_intel = contact_intel_data.get(v)
            
            if contact_intel:
                # Format network diversity with color coding
                portfolio_div = contact_intel.get('portfolio_diversity', '')
                intelligence_formatted['network_diversity'] = self._format_intelligence_rating(portfolio_div)
                
                # Format geographic diversity with color coding
                geo_risk = contact_intel.get('geographic_risk', '')
                intelligence_formatted['geographic_diversity'] = self._format_intelligence_rating(geo_risk)
                
                # Format infrastructure diversity with color coding
                infra_risk = contact_intel.get('infrastructure_risk', '')
                intelligence_formatted['infrastructure_diversity'] = self._format_intelligence_rating(infra_risk)
                
                # Copy other intelligence fields
                intelligence_formatted['measurement_status'] = contact_intel.get('measurement_status', '')
                intelligence_formatted['performance_status'] = contact_intel.get('performance_status', '')
                intelligence_formatted['performance_underutilized'] = contact_intel.get('performance_underutilized', 0)
                intelligence_formatted['performance_underutilized_percentage'] = contact_intel.get('performance_underutilized_percentage', 0)
                intelligence_formatted['performance_underutilized_fps'] = contact_intel.get('performance_underutilized_fps', [])
                # Add new CW/BW ratio fields
                intelligence_formatted['performance_operator_overall_ratio'] = contact_intel.get('performance_operator_overall_ratio', '')
                intelligence_formatted['performance_operator_guard_ratio'] = contact_intel.get('performance_operator_guard_ratio', '')
                intelligence_formatted['performance_operator_exit_ratio'] = contact_intel.get('performance_operator_exit_ratio', '')
                intelligence_formatted['performance_network_overall_ratio'] = contact_intel.get('performance_network_overall_ratio', '')
                intelligence_formatted['performance_network_guard_ratio'] = contact_intel.get('performance_network_guard_ratio', '')
                intelligence_formatted['performance_network_exit_ratio'] = contact_intel.get('performance_network_exit_ratio', '')
                intelligence_formatted['performance_network_overall_median'] = contact_intel.get('performance_network_overall_median', '')
                intelligence_formatted['performance_network_guard_median'] = contact_intel.get('performance_network_guard_median', '')
                intelligence_formatted['performance_network_exit_median'] = contact_intel.get('performance_network_exit_median', '')
                intelligence_formatted['performance_operator_overall_pct'] = contact_intel.get('performance_operator_overall_pct', '')
                intelligence_formatted['performance_operator_guard_pct'] = contact_intel.get('performance_operator_guard_pct', '')
                intelligence_formatted['performance_operator_exit_pct'] = contact_intel.get('performance_operator_exit_pct', '')
                intelligence_formatted['performance_relay_count'] = contact_intel.get('performance_relay_count', 0)
                intelligence_formatted['maturity'] = contact_intel.get('maturity', '')
        
        # 4. Version compliance and version status counting (reuse existing relay counting patterns)
        # Count version compliance: recommended_version=true for compliant, =false for non-compliant, not set/empty for unknown
        version_compliant = sum(1 for relay in members if relay.get('recommended_version') is True)
        version_not_compliant = sum(1 for relay in members if relay.get('recommended_version') is False)
        version_unknown = sum(1 for relay in members if relay.get('recommended_version') is None)
        
        # Count version status: recommended, experimental, obsolete, new in series, unrecommended
        version_status_counts = {
            'recommended': sum(1 for relay in members if relay.get('version_status') == 'recommended'),
            'experimental': sum(1 for relay in members if relay.get('version_status') == 'experimental'),
            'obsolete': sum(1 for relay in members if relay.get('version_status') == 'obsolete'),
            'new_in_series': sum(1 for relay in members if relay.get('version_status') == 'new in series'),
            'unrecommended': sum(1 for relay in members if relay.get('version_status') == 'unrecommended')
        }
        
        # Collect actual Tor versions for each status category (for tooltips)
        version_status_versions = {
            'recommended': set(),
            'experimental': set(),
            'obsolete': set(),
            'new_in_series': set(),
            'unrecommended': set()
        }
        
        for relay in members:
            status = relay.get('version_status')
            version = relay.get('version')
            if status and version:
                if status == 'new in series':
                    version_status_versions['new_in_series'].add(version)
                elif status in version_status_versions:
                    version_status_versions[status].add(version)
        
        # Format version compliance display (only show non-zero values for not compliant and unknown)
        # Add status indicators based on compliance ratio
        total_relays = len(members)
        
        if total_relays == 0:
            # Edge case: no relays
            intelligence_formatted['version_compliance'] = '0 compliant'
        elif version_compliant == total_relays:
            # All relays are compliant (recommended_version=True)
            intelligence_formatted['version_compliance'] = f'<span style="color: #2e7d2e; font-weight: bold;">All</span>, {version_compliant} (100%) compliant'
        elif version_compliant > 0 and (version_compliant / total_relays) > 0.5:
            # More than 50% are compliant
            compliant_pct = round((version_compliant / total_relays) * 100)
            result = f'<span style="color: #cc9900; font-weight: bold;">Partial</span>, {version_compliant} ({compliant_pct}%) compliant'
            # Add non-zero counts for not compliant and unknown
            parts = []
            if version_not_compliant > 0:
                not_compliant_pct = round((version_not_compliant / total_relays) * 100)
                parts.append(f"{version_not_compliant} ({not_compliant_pct}%) not compliant")
            if version_unknown > 0:
                unknown_pct = round((version_unknown / total_relays) * 100)
                parts.append(f"{version_unknown} ({unknown_pct}%) unknown")
            if parts:
                result += ', ' + ', '.join(parts)
            intelligence_formatted['version_compliance'] = result
        else:
            # 50% or less are compliant (or no compliant relays)
            compliant_pct = round((version_compliant / total_relays) * 100) if total_relays > 0 else 0
            result = f'<span style="color: #c82333; font-weight: bold;">Poor</span>, {version_compliant} ({compliant_pct}%) compliant'
            # Add non-zero counts for not compliant and unknown
            parts = []
            if version_not_compliant > 0:
                not_compliant_pct = round((version_not_compliant / total_relays) * 100)
                parts.append(f"{version_not_compliant} ({not_compliant_pct}%) not compliant")
            if version_unknown > 0:
                unknown_pct = round((version_unknown / total_relays) * 100)
                parts.append(f"{version_unknown} ({unknown_pct}%) unknown")
            if parts:
                result += ', ' + ', '.join(parts)
            intelligence_formatted['version_compliance'] = result
        
        # Format version status display (only show counts > 0) with version tooltips and percentages
        # Add status indicators based on recommended status ratio (similar to version compliance)
        version_status_parts = []
        version_status_tooltips = {}
        
        recommended_count = version_status_counts.get('recommended', 0)
        
        # Create tooltips for all status categories (including recommended)
        for status, count in version_status_counts.items():
            if count > 0:
                status_display = status.replace('_', ' ')  # Convert new_in_series to "new in series"
                
                # Create tooltip with actual Tor versions
                versions = sorted(list(version_status_versions[status]))
                if versions:
                    tooltip_status = status_display.capitalize()
                    version_status_tooltips[status] = f"{tooltip_status} versions: {', '.join(versions)}"
                else:
                    version_status_tooltips[status] = f"{status_display.capitalize()} versions: (no version data)"
        
        # Format with status indicator based on recommended percentage
        if total_relays == 0:
            # Edge case: no relays
            intelligence_formatted['version_status'] = 'none'
        elif recommended_count == total_relays:
            # All relays have recommended status
            recommended_tooltip = version_status_tooltips.get('recommended', 'All relays have recommended versions')
            intelligence_formatted['version_status'] = f'<span style="color: #2e7d2e; font-weight: bold;">All</span>, <span title="{recommended_tooltip}" style="cursor: help;">{recommended_count} (100%) recommended</span>'
        elif recommended_count > 0 and (recommended_count / total_relays) > 0.5:
            # More than 50% have recommended status
            recommended_pct = round((recommended_count / total_relays) * 100)
            recommended_tooltip = version_status_tooltips.get('recommended', 'Recommended versions')
            result = f'<span style="color: #cc9900; font-weight: bold;">Partial</span>, <span title="{recommended_tooltip}" style="cursor: help;">{recommended_count} ({recommended_pct}%) recommended</span>'
            
            # Add other status counts with tooltips
            other_parts = []
            for status, count in version_status_counts.items():
                if status != 'recommended' and count > 0:
                    status_display = status.replace('_', ' ')  # Convert new_in_series to "new in series"
                    status_pct = round((count / total_relays) * 100)
                    tooltip = version_status_tooltips.get(status, f'{status_display.capitalize()} versions')
                    other_parts.append(f'<span title="{tooltip}" style="cursor: help;">{count} ({status_pct}%) {status_display}</span>')
            
            if other_parts:
                result += ', ' + ', '.join(other_parts)
            intelligence_formatted['version_status'] = result
        else:
            # 50% or less have recommended status (or no recommended relays)
            recommended_pct = round((recommended_count / total_relays) * 100) if total_relays > 0 else 0
            recommended_tooltip = version_status_tooltips.get('recommended', 'Recommended versions')
            result = f'<span style="color: #c82333; font-weight: bold;">Poor</span>, <span title="{recommended_tooltip}" style="cursor: help;">{recommended_count} ({recommended_pct}%) recommended</span>'
            
            # Add other status counts with tooltips
            other_parts = []
            for status, count in version_status_counts.items():
                if status != 'recommended' and count > 0:
                    status_display = status.replace('_', ' ')  # Convert new_in_series to "new in series"
                    status_pct = round((count / total_relays) * 100)
                    tooltip = version_status_tooltips.get(status, f'{status_display.capitalize()} versions')
                    other_parts.append(f'<span title="{tooltip}" style="cursor: help;">{count} ({status_pct}%) {status_display}</span>')
            
            if other_parts:
                result += ', ' + ', '.join(other_parts)
            intelligence_formatted['version_status'] = result
        
        intelligence_formatted['version_status_tooltips'] = version_status_tooltips
        
        display_data['operator_intelligence'] = intelligence_formatted
        
        # 5. Overall uptime formatting with green highlighting
        uptime_formatted = {}
        if operator_reliability and operator_reliability.get('overall_uptime'):
            for period, data in operator_reliability['overall_uptime'].items():
                avg = data.get('average', 0)
                display_name = data.get('display_name', period)
                relay_count = data.get('relay_count', 0)
                
                # Fix floating point comparison by using >= 99.99 instead of == 100.0
                # Also handle cases where avg is exactly 100.0 or very close due to floating point precision
                if avg >= 99.99 or abs(avg - 100.0) < 0.01:
                    uptime_formatted[period] = {
                        'display': f'<span style="color: #28a745; font-weight: bold;">{display_name} {avg:.1f}%</span>',
                        'relay_count': relay_count
                    }
                else:
                    uptime_formatted[period] = {
                        'display': f'{display_name} {avg:.1f}%',
                        'relay_count': relay_count
                    }
        
        display_data['uptime_formatted'] = uptime_formatted
        
        # 5.1. Network Uptime Percentiles formatting (6-month period)
        network_percentiles_formatted = {}
        if operator_reliability and operator_reliability.get('network_uptime_percentiles'):
            network_data = operator_reliability['network_uptime_percentiles']
            six_month_data = operator_reliability.get('overall_uptime', {}).get('6_months', {})
            
            if network_data and six_month_data:
                from .uptime_utils import format_network_percentiles_display, find_operator_percentile_position
                
                operator_avg = six_month_data.get('average', 0)
                total_network_relays = network_data.get('total_relays', 0)
                
                # Get operator's percentile range for dynamic tooltip
                position_info = find_operator_percentile_position(operator_avg, network_data)
                percentile_range = position_info.get('percentile_range', 'unknown')
                
                # Use the simplified display formatting function
                percentile_display = format_network_percentiles_display(network_data, operator_avg)
                
                if percentile_display:
                    # Create enhanced tooltip with statistical methodology explanation
                    if percentile_range != 'unknown':
                        tooltip_text = f"Statistical distribution of 6-month uptime performance across {total_network_relays:,} network relays. Each relay's daily uptime values are averaged over 6 months, then percentile ranks show performance quartiles. This operator falls in the {percentile_range} percentile range of network reliability."
                    else:
                        tooltip_text = f"Statistical distribution of 6-month uptime performance across {total_network_relays:,} network relays. Each relay's daily uptime values are averaged over 6 months, then percentile ranks show performance quartiles."
                    
                    network_percentiles_formatted = {
                        'display': percentile_display,
                        'total_network_relays': total_network_relays,
                        'percentile_range': percentile_range,
                        'tooltip': tooltip_text
                    }
        
        display_data['network_percentiles_formatted'] = network_percentiles_formatted
        
        # 6. Outliers calculations and formatting
        outliers_data = {}
        if operator_reliability and operator_reliability.get('outliers'):
            total_outliers = len(operator_reliability['outliers'].get('low_outliers', [])) + len(operator_reliability['outliers'].get('high_outliers', []))
            total_relays = operator_reliability.get('total_relays', 1)
            
            if total_outliers > 0:
                outlier_percentage = (total_outliers / total_relays * 100) if total_relays > 0 else 0
                
                # Get statistics for tooltip
                six_month_data = operator_reliability.get('overall_uptime', {}).get('6_months', {})
                mean_uptime = six_month_data.get('average', 0)
                std_dev = six_month_data.get('std_dev', 0)
                two_sigma_threshold = mean_uptime - (2 * std_dev)
                
                outliers_data['total_count'] = total_outliers
                outliers_data['total_relays'] = total_relays
                outliers_data['percentage'] = f"{outlier_percentage:.1f}"
                outliers_data['tooltip'] = f"6mo: ≥2σ {two_sigma_threshold:.1f}% from μ {mean_uptime:.1f}%"
                
                # Format low outliers
                low_outliers = operator_reliability['outliers'].get('low_outliers', [])
                if low_outliers:
                    low_names = [f"{o['nickname']} ({o['uptime']:.1f}%)" for o in low_outliers]
                    outliers_data['low_count'] = len(low_outliers)
                    outliers_data['low_tooltip'] = ', '.join(low_names)
                
                # Format high outliers  
                high_outliers = operator_reliability['outliers'].get('high_outliers', [])
                if high_outliers:
                    high_names = [f"{o['nickname']} ({o['uptime']:.1f}%)" for o in high_outliers]
                    outliers_data['high_count'] = len(high_outliers)
                    outliers_data['high_tooltip'] = ', '.join(high_names)
            else:
                outliers_data['none_detected'] = True
        
        display_data['outliers'] = outliers_data
        
        # 7. Uptime data timestamp (reuse existing uptime data)
        uptime_timestamp = None
        uptime_data = getattr(self, 'uptime_data', None)
        if uptime_data and uptime_data.get('relays_published'):
            uptime_timestamp = uptime_data['relays_published'] + ' UTC'
        display_data['uptime_timestamp'] = uptime_timestamp
        
        # 8. Real-time downtime alerts (idea #8 from uptime integration proposals)
        downtime_alerts = self._calculate_operator_downtime_alerts(v, members, i, bandwidth_unit)
        display_data['downtime_alerts'] = downtime_alerts
        
        # 9. Flag analysis
        operator_flag_analysis = self._compute_contact_flag_analysis(v, members)
        display_data['flag_analysis'] = operator_flag_analysis
        
        # 10. Flag bandwidth analysis
        operator_flag_bandwidth_analysis = self._compute_contact_flag_bandwidth_analysis(v, members)
        display_data['flag_bandwidth_analysis'] = operator_flag_bandwidth_analysis
        
        return display_data
    
    def _compute_contact_flag_analysis(self, contact_hash, members):
        """
        Compute flag reliability analysis for contact operator using consolidated uptime data.
        
        This method uses pre-computed results from _reprocess_uptime_data(). If consolidated
        processing isn't available, no flag data is returned (section won't be shown).
        
        Args:
            contact_hash: Contact hash for the operator
            members: List of relay objects for the operator
            
        Returns:
            dict: Flag reliability analysis data or indication that no data is available
        """
        try:
            # Use consolidated uptime results if available (from _reprocess_uptime_data)
            if hasattr(self, '_consolidated_uptime_results'):
                consolidated_results = self._consolidated_uptime_results
                relay_uptime_data = consolidated_results['relay_uptime_data']
                network_flag_statistics = consolidated_results.get('network_flag_statistics', {})
                
                # Extract flag data for operator relays using pre-computed data
                operator_flag_data = {}
                
                for relay in members:
                    fingerprint = relay.get('fingerprint', '')
                    nickname = relay.get('nickname', 'Unknown')
                    
                    # Get actual flags this relay currently has (same approach as line 561)
                    relay_flags = set(relay.get('flags', []))
                    
                    if fingerprint in relay_uptime_data:
                        flag_data = relay_uptime_data[fingerprint]['flag_data']
                        
                        for flag, periods in flag_data.items():
                            # Only include flag data for flags the relay currently has
                            if flag in relay_flags:
                                if flag not in operator_flag_data:
                                    operator_flag_data[flag] = {}
                                for period, data in periods.items():
                                    if period not in operator_flag_data[flag]:
                                        operator_flag_data[flag][period] = []
                                    operator_flag_data[flag][period].append({
                                        'relay_nickname': data['relay_info']['nickname'],
                                        'relay_fingerprint': data['relay_info']['fingerprint'],
                                        'uptime': data['uptime'],
                                        'data_points': data['data_points']
                                    })
                
                if not operator_flag_data:
                    return {'has_flag_data': False, 'error': 'No flag data available for operator relays'}
                
                # Process flag reliability using pre-computed network statistics
                flag_reliability_results = self._process_operator_flag_reliability(
                    operator_flag_data, network_flag_statistics
                )
                
                return {
                    'has_flag_data': True,
                    'flag_reliabilities': flag_reliability_results['flag_reliabilities'],
                    'available_periods': flag_reliability_results['available_periods'],
                    'period_display': flag_reliability_results['period_display'],
                    'source': 'consolidated_processing'
                }
                
            else:
                # No consolidated results available - don't show flag reliability section
                return {'has_flag_data': False, 'error': 'Consolidated uptime processing not available'}
                
        except Exception as e:
            return {
                'has_flag_data': False, 
                'error': f'Flag analysis processing failed: {str(e)}',
                'source': 'error'
            }
    
    def _compute_contact_flag_bandwidth_analysis(self, contact_hash, members):
        """
        Compute flag bandwidth analysis for contact operator using consolidated bandwidth data.
        
        This method uses pre-computed results from _reprocess_bandwidth_data(). If consolidated
        processing isn't available, no flag bandwidth data is returned.
        
        Args:
            contact_hash: Contact hash for the operator
            members: List of relay objects for the operator
            
        Returns:
            dict: Flag bandwidth analysis data or indication that no data is available
        """
        try:
            # Use consolidated bandwidth results if available (from _reprocess_bandwidth_data)
            if not hasattr(self, '_consolidated_bandwidth_results'):
                return {'has_flag_data': False, 'error': 'Consolidated bandwidth processing not available'}
            
            consolidated_results = self._consolidated_bandwidth_results
            if not consolidated_results:
                return {'has_flag_data': False, 'error': 'Consolidated bandwidth results are None'}
            
            relay_bandwidth_data = consolidated_results['relay_bandwidth_data']
            network_flag_statistics = consolidated_results.get('network_flag_statistics', {})
            
            # Extract flag bandwidth data for operator relays using pre-computed data
            operator_flag_data = {}
            
            for relay in members:
                fingerprint = relay.get('fingerprint', '')
                nickname = relay.get('nickname', 'Unknown')
                
                # Get actual flags this relay currently has
                relay_flags = set(relay.get('flags', []))
                
                if fingerprint in relay_bandwidth_data:
                    flag_data = relay_bandwidth_data[fingerprint]['flag_data']
                    
                    for flag, bandwidth_averages in flag_data.items():
                        # Only include flag data for flags the relay currently has
                        if flag in relay_flags:
                            if flag not in operator_flag_data:
                                operator_flag_data[flag] = {}
                            for period in ['6_months', '1_year', '5_years']:
                                if period in bandwidth_averages and bandwidth_averages[period] > 0:
                                    if period not in operator_flag_data[flag]:
                                        operator_flag_data[flag][period] = []
                                    operator_flag_data[flag][period].append({
                                        'relay_nickname': nickname,
                                        'relay_fingerprint': fingerprint,
                                        'bandwidth': bandwidth_averages[period],
                                        'data_points': 0  # Not tracked in simplified structure
                                    })
            
            if not operator_flag_data:
                return {'has_flag_data': False, 'error': 'No flag bandwidth data available for operator relays'}
                
            # Process flag bandwidth reliability using pre-computed network statistics
            flag_bandwidth_results = self._process_operator_flag_bandwidth_reliability(
                operator_flag_data, network_flag_statistics
            )
            
            return {
                'has_flag_data': True,
                'flag_reliabilities': flag_bandwidth_results['flag_reliabilities'],
                'available_periods': flag_bandwidth_results['available_periods'],
                'period_display': flag_bandwidth_results['period_display'],
                'source': 'consolidated_processing'
            }
                
        except Exception as e:
            return {
                'has_flag_data': False, 
                'error': f'Flag bandwidth analysis processing failed: {str(e)}',
                'source': 'error'
            }
    
    def _process_operator_flag_bandwidth_reliability(self, operator_flag_data, network_flag_statistics):
        """
        Process operator flag bandwidth data into display format with color coding.
        Mirrors the uptime flag processing but for bandwidth metrics.
        
        Args:
            operator_flag_data (dict): Flag bandwidth data for the operator
            network_flag_statistics (dict): Network-wide flag bandwidth statistics
            
        Returns:
            dict: Processed flag bandwidth data for template display
        """
        flag_reliabilities = {}
        periods_with_data = set()
        
        # Flag processing order (Exit > Guard > Fast > Running)
        flag_order = ['Exit', 'Guard', 'Fast', 'Running', 'Authority', 'HSDir', 'Stable', 'V2Dir']
        
        # Flag display configuration
        flag_display_mapping = {
            'Exit': {'icon': '🚪', 'display_name': 'Exit Node'},
            'Guard': {'icon': '🛡️', 'display_name': 'Entry Guard'},
            'Fast': {'icon': '⚡', 'display_name': 'Fast Relay'},
            'Running': {'icon': '🟢', 'display_name': 'Running'},
            'Authority': {'icon': '👑', 'display_name': 'Directory Authority'},
            'HSDir': {'icon': '📁', 'display_name': 'Hidden Service Directory'},
            'Stable': {'icon': '🎯', 'display_name': 'Stable Relay'},
            'V2Dir': {'icon': '📋', 'display_name': 'Version 2 Directory'}
        }
        
        # Process flags in the specified order
        for flag in flag_order:
            if flag not in operator_flag_data:
                continue
                
            periods = operator_flag_data[flag]
            
            if flag not in flag_display_mapping:
                continue
                
            flag_info = {
                'icon': flag_display_mapping[flag]['icon'],
                'display_name': flag_display_mapping[flag]['display_name'],
                'periods': {}
            }
            
            for period in ['6_months', '1_year', '5_years']:
                # Map to short period names for display
                if period == '6_months':
                    period_short = '6M'
                elif period == '1_year':
                    period_short = '1Y'
                elif period == '5_years':
                    period_short = '5Y'
                else:
                    period_short = period  # fallback
                
                if period in periods and periods[period]:
                    # Calculate average bandwidth for operator relays with this flag
                    bandwidth_values = [relay_data['bandwidth'] for relay_data in periods[period]]
                    avg_bandwidth = sum(bandwidth_values) / len(bandwidth_values)
                    
                    # Include all values >= 0 (0 is valid data meaning relay had no bandwidth)
                    if avg_bandwidth >= 0:
                        periods_with_data.add(period_short)
                        
                        # Format bandwidth for display
                        unit = self.bandwidth_formatter.determine_unit(avg_bandwidth)
                        formatted_bw = self.bandwidth_formatter.format_bandwidth_with_unit(avg_bandwidth, unit)
                        bandwidth_display = f"{formatted_bw} {unit}"
                        
                        # Determine color coding and tooltip
                        color_class = ''  # Default: no special coloring (black text)
                        tooltip = f'{flag} flag bandwidth over {period_short}: {bandwidth_display}'
                        
                        # Add network comparison if available
                        if (flag in network_flag_statistics and 
                            period in network_flag_statistics[flag] and
                            network_flag_statistics[flag][period]):
                            
                            net_stats = network_flag_statistics[flag][period]
                            net_mean_unit = self.bandwidth_formatter.determine_unit(net_stats["mean"])
                            net_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(net_stats["mean"], net_mean_unit)
                            tooltip += f' (network μ: {net_mean_formatted} {net_mean_unit})'
                            
                            # Enhanced color coding logic for bandwidth - match legend
                            if avg_bandwidth <= net_stats['two_sigma_low']:
                                color_class = 'statistical-outlier-low'  # Red - Poor (≥2σ from network μ)
                            elif avg_bandwidth > net_stats['mean'] * 1.5:  # High performance threshold
                                color_class = 'high-performance'  # Green - High performance (>1.5x μ)
                            elif avg_bandwidth < net_stats['mean']:
                                color_class = 'below-mean'  # Yellow - Below average (<μ of network)
                            # EXPLICIT: Values between mean and 1.5x mean get no color_class (black)
                        
                        else:
                            # Fallback color coding when no network statistics available
                            if avg_bandwidth <= 0:
                                color_class = 'statistical-outlier-low'
                            # Default: no special coloring (black)
                        
                        flag_info['periods'][period_short] = {
                            'value': avg_bandwidth,
                            'value_display': bandwidth_display,
                            'color_class': color_class,
                            'tooltip': tooltip,
                            'relay_count': len(periods[period])
                        }
                
            # Only include flag if it has data for at least one period
            if flag_info['periods']:
                flag_reliabilities[flag] = flag_info
        
        # Generate dynamic period display string
        period_order = ['6M', '1Y', '5Y']
        available_periods = [p for p in period_order if p in periods_with_data]
        period_display = '/'.join(available_periods) if available_periods else 'No Data'
        
        return {
            'flag_reliabilities': flag_reliabilities,
            'available_periods': available_periods,
            'period_display': period_display,
            'has_data': bool(available_periods)
        }
    
    def _process_operator_flag_reliability(self, operator_flag_data, network_flag_statistics):
        """
        Process flag reliability metrics for an operator using pre-computed network statistics.
        
        Args:
            operator_flag_data: Operator's flag-specific uptime data
            network_flag_statistics: Network-wide flag statistics for comparison
            
        Returns:
            dict: Processed flag reliability metrics with available periods info
        """
        flag_display_mapping = {
            'Running': {'icon': '🟢', 'display_name': 'Running Operation'},
            'Fast': {'icon': '⚡', 'display_name': 'Fast Relay'},
            'Stable': {'icon': '🛡️', 'display_name': 'Stable Operation'}, 
            'Guard': {'icon': '🛡️', 'display_name': 'Entry Guard'},
            'Exit': {'icon': '🚪', 'display_name': 'Exit Node'},
            'HSDir': {'icon': '📂', 'display_name': 'Hidden Services'},
            'Authority': {'icon': '⚖️', 'display_name': 'Directory Authority'},
            'V2Dir': {'icon': '📁', 'display_name': 'Directory Services'},
            'BadExit': {'icon': '🚫', 'display_name': 'Bad Exit'}
        }
        
        # Define flag ordering for consistent display - Hidden Services before Directory Services
        flag_order = ['BadExit', 'Stable', 'Fast', 'Running', 'Authority', 'Guard', 'Exit', 'HSDir', 'V2Dir']
        
        flag_reliabilities = {}
        
        # Track which time periods have data across all flags
        periods_with_data = set()
        
        # Process flags in the specified order
        for flag in flag_order:
            if flag not in operator_flag_data:
                continue
                
            periods = operator_flag_data[flag]
            
            if flag not in flag_display_mapping:
                continue
                
            flag_info = {
                'icon': flag_display_mapping[flag]['icon'],
                'display_name': flag_display_mapping[flag]['display_name'],
                'periods': {}
            }
            
            for period in ['1_month', '6_months', '1_year', '5_years']:
                # Fixed period mapping - handle months before month to avoid conflict
                if period == '1_month':
                    period_short = '1M'
                elif period == '6_months':
                    period_short = '6M'
                elif period == '1_year':
                    period_short = '1Y'
                elif period == '5_years':
                    period_short = '5Y'
                else:
                    period_short = period  # fallback
                
                if period in periods and periods[period]:
                    # Calculate average uptime for operator relays with this flag
                    uptime_values = [relay_data['uptime'] for relay_data in periods[period]]
                    avg_uptime = sum(uptime_values) / len(uptime_values)
                    
                    # Include all values >= 0 (0% is valid data meaning relay never had this flag)
                    if avg_uptime >= 0:
                        periods_with_data.add(period_short)
                        
                        # Determine color coding and tooltip
                        color_class = ''
                        tooltip = f'{flag} flag uptime over {period_short}: {avg_uptime:.1f}%'
                        
                        # Add network comparison if available
                        if (flag in network_flag_statistics and 
                            period in network_flag_statistics[flag] and
                            network_flag_statistics[flag][period]):
                            
                            net_stats = network_flag_statistics[flag][period]
                            tooltip += f' (network μ: {net_stats["mean"]:.1f}%, 2σ: {net_stats["two_sigma_low"]:.1f}%)'
                            
                            # Enhanced color coding logic: prioritize statistical outliers over >99%
                            # Special handling for very low values (≤1%) - likely to be statistical outliers
                            if avg_uptime <= 1.0:
                                color_class = 'statistical-outlier-low'
                            elif avg_uptime <= net_stats['two_sigma_low']:
                                color_class = 'statistical-outlier-low'
                            elif avg_uptime >= 99.0:
                                color_class = 'high-performance'
                            elif avg_uptime > net_stats['two_sigma_high']:
                                color_class = 'statistical-outlier-high'
                            elif avg_uptime < net_stats['mean']:
                                color_class = 'below-mean'
                            # Note: Removed default above-mean green coloring per user feedback
                        
                        else:
                            # Fallback color coding when no network statistics available
                            if avg_uptime <= 1.0:
                                color_class = 'statistical-outlier-low'
                            elif avg_uptime >= 99.0:
                                color_class = 'high-performance'
                            # Default: no special coloring
                        
                        flag_info['periods'][period_short] = {
                            'value': avg_uptime,
                            'color_class': color_class,
                            'tooltip': tooltip,
                            'relay_count': len(periods[period])
                        }
                
            # Only include flag if it has data for at least one period
            if flag_info['periods']:
                flag_reliabilities[flag] = flag_info
        
        # Generate dynamic period display string
        period_order = ['1M', '6M', '1Y', '5Y']
        available_periods = [p for p in period_order if p in periods_with_data]
        period_display = '/'.join(available_periods) if available_periods else 'No Data'
        
        return {
            'flag_reliabilities': flag_reliabilities,
            'available_periods': available_periods,
            'period_display': period_display,
            'has_data': bool(available_periods)
        }
    
    def _calculate_operator_downtime_alerts(self, contact_hash, operator_relays, contact_data, bandwidth_unit):
        """
        Calculate real-time downtime alerts for operator contact pages.
        
        Shows offline relays by type with traffic percentages and impact calculations.
        Implements idea #8 from uptime integration proposals.
        
        Args:
            contact_hash (str): Contact hash for the operator  
            operator_relays (list): List of relay objects for this operator
            contact_data (dict): Pre-computed contact statistics (guard_count, bandwidth, etc.)
            bandwidth_unit (str): Bandwidth unit for display (MB/s, GB/s, etc.)
            
        Returns:
            dict: Downtime alert data with offline counts, impact metrics, and tooltips
        """
        if not operator_relays:
            return None
        
        downtime_alerts = {
            'offline_counts': {
                'guard': 0,
                'middle': 0, 
                'exit': 0
            },
            'offline_bandwidth_impact': {
                'total_offline_bandwidth': 0,  # bytes
                'total_offline_bandwidth_formatted': '0.00',  # formatted with unit
                'offline_bandwidth_percentage': 0.0,  # percentage of operator's total bandwidth
                'total_operator_bandwidth_formatted': '0.00'  # formatted operator total
            },
            'offline_consensus_weight_impact': {
                'total_offline_cw_fraction': 0.0,  # fraction of network consensus weight
                'offline_cw_percentage_of_operator': 0.0,  # percentage of operator's total CW  
                'total_operator_cw_percentage': 0.0  # operator's total network influence
            },
            'offline_relay_details': {
                'guard_relays': [],  # List of offline guard relays with last_seen
                'middle_relays': [],  # List of offline middle relays with last_seen  
                'exit_relays': []   # List of offline exit relays with last_seen
            },
            'has_offline_relays': False
        }
        
        # Calculate network totals for percentage calculations (validation method 1)
        if not hasattr(self, 'json') or not self.json.get('network_totals'):
            return downtime_alerts
            
        network_totals = self.json['network_totals']
        total_network_guard_cw = network_totals.get('guard_consensus_weight', 0)
        total_network_middle_cw = network_totals.get('middle_consensus_weight', 0) 
        total_network_exit_cw = network_totals.get('exit_consensus_weight', 0)
        total_network_cw = total_network_guard_cw + total_network_middle_cw + total_network_exit_cw
        
        # Calculate operator totals for impact percentage calculations (validation method 2)
        operator_total_bandwidth = contact_data.get('bandwidth', 0)  # bytes
        operator_total_cw_fraction = contact_data.get('consensus_weight_fraction', 0.0)
        
        # Track offline totals for impact calculations
        total_offline_bandwidth = 0
        total_offline_cw_fraction = 0.0
        
        # Process each relay to check if offline and categorize by flags
        for relay in operator_relays:
            # Check if relay is offline (not running)
            if not relay.get('running', False):
                downtime_alerts['has_offline_relays'] = True
                
                # Get relay basic info
                nickname = relay.get('nickname', 'Unknown')
                fingerprint = relay.get('fingerprint', '')
                last_seen = relay.get('last_seen', 'Unknown')
                observed_bandwidth = relay.get('observed_bandwidth', 0)
                consensus_weight = relay.get('consensus_weight', 0)
                flags = relay.get('flags', [])
                
                # Format last seen time using existing utility
                if last_seen and last_seen != 'Unknown':
                    last_seen_formatted = self._format_time_ago(last_seen)
                else:
                    last_seen_formatted = 'Unknown'
                
                # Add to total offline impact calculations
                total_offline_bandwidth += observed_bandwidth
                
                # Convert consensus weight to fraction for network percentage calculation
                if total_network_cw > 0:
                    relay_cw_fraction = consensus_weight / total_network_cw
                    total_offline_cw_fraction += relay_cw_fraction
                
                # Create relay info for tooltips
                relay_info = {
                    'nickname': nickname,
                    'fingerprint': fingerprint[:8],  # Short fingerprint for display
                    'last_seen': last_seen_formatted,
                    'bandwidth': observed_bandwidth,
                    'consensus_weight': consensus_weight,
                    'display_text': f"{nickname} ({last_seen_formatted})"
                }
                
                # Categorize by relay type based on flags
                if 'Guard' in flags:
                    downtime_alerts['offline_counts']['guard'] += 1
                    downtime_alerts['offline_relay_details']['guard_relays'].append(relay_info)
                    
                if 'Exit' in flags:
                    downtime_alerts['offline_counts']['exit'] += 1  
                    downtime_alerts['offline_relay_details']['exit_relays'].append(relay_info)
                    
                # Middle relays are all relays that aren't Guard or Exit only, or relays that are both
                # This matches the logic used elsewhere in the codebase for middle relay classification
                if not flags or ('Guard' not in flags and 'Exit' not in flags) or ('Guard' in flags and 'Exit' in flags):
                    downtime_alerts['offline_counts']['middle'] += 1
                    downtime_alerts['offline_relay_details']['middle_relays'].append(relay_info)
        
        # Calculate bandwidth impact metrics
        if operator_total_bandwidth > 0:
            offline_bandwidth_percentage = (total_offline_bandwidth / operator_total_bandwidth) * 100
        else:
            offline_bandwidth_percentage = 0.0
            
        downtime_alerts['offline_bandwidth_impact'] = {
            'total_offline_bandwidth': total_offline_bandwidth,
            'total_offline_bandwidth_formatted': self.bandwidth_formatter.format_bandwidth_with_unit(total_offline_bandwidth, bandwidth_unit),
            'offline_bandwidth_percentage': offline_bandwidth_percentage,
            'total_operator_bandwidth_formatted': self.bandwidth_formatter.format_bandwidth_with_unit(operator_total_bandwidth, bandwidth_unit)
        }
        
        # Calculate consensus weight impact metrics  
        if operator_total_cw_fraction > 0:
            offline_cw_percentage_of_operator = (total_offline_cw_fraction / operator_total_cw_fraction) * 100
        else:
            offline_cw_percentage_of_operator = 0.0
            
        downtime_alerts['offline_consensus_weight_impact'] = {
            'total_offline_cw_fraction': total_offline_cw_fraction,
            'total_offline_cw_percentage': total_offline_cw_fraction * 100,  # Network percentage
            'offline_cw_percentage_of_operator': offline_cw_percentage_of_operator,
            'total_operator_cw_percentage': operator_total_cw_fraction * 100
        }
        
        # Calculate traffic percentages for each relay type (validation against operator totals)
        # This provides the "X% of observed traffic" metrics requested
        guard_traffic_percentage = 0.0
        middle_traffic_percentage = 0.0
        exit_traffic_percentage = 0.0
        
        if contact_data.get('guard_bandwidth', 0) > 0:
            guard_offline_bandwidth = sum(r['bandwidth'] for r in downtime_alerts['offline_relay_details']['guard_relays'])
            guard_traffic_percentage = (guard_offline_bandwidth / contact_data['guard_bandwidth']) * 100
            
        if contact_data.get('middle_bandwidth', 0) > 0:
            middle_offline_bandwidth = sum(r['bandwidth'] for r in downtime_alerts['offline_relay_details']['middle_relays'])
            middle_traffic_percentage = (middle_offline_bandwidth / contact_data['middle_bandwidth']) * 100
            
        if contact_data.get('exit_bandwidth', 0) > 0:
            exit_offline_bandwidth = sum(r['bandwidth'] for r in downtime_alerts['offline_relay_details']['exit_relays'])
            exit_traffic_percentage = (exit_offline_bandwidth / contact_data['exit_bandwidth']) * 100
        
        # Add traffic percentages to offline counts for display
        downtime_alerts['traffic_percentages'] = {
            'guard': guard_traffic_percentage,
            'middle': middle_traffic_percentage,
            'exit': exit_traffic_percentage
        }
        
        return downtime_alerts

    def _calculate_uptime_display(self, relay):
        """
        Calculate uptime/downtime display for a single relay.
        
        Logic:
        - For running relays: Show uptime from last_restarted
        - For offline relays: Show downtime from last_seen (avoids incorrect long downtimes)
        
        Args:
            relay (dict): Relay data dictionary
            
        Returns:
            str: Formatted uptime display (e.g., "UP 2d 5h ago", "DOWN 3h 45m ago", "Unknown")
        """
        if not relay.get('last_restarted'):
            return "Unknown"
            
        is_running = relay.get('running', False)
        
        if is_running:
            # For running relays, show uptime from last_restarted
            time_since_restart = self._format_time_ago(relay['last_restarted'])
            if time_since_restart and time_since_restart != "unknown":
                return f"UP {time_since_restart}"
            else:
                return "Unknown"
        else:
            # For offline relays, show downtime from last_seen (when it was last observed online)
            # This avoids showing incorrect long downtimes based on old last_restarted timestamps
            if relay.get('last_seen'):
                time_since_last_seen = self._format_time_ago(relay['last_seen'])
                if time_since_last_seen and time_since_last_seen != "unknown":
                    return f"DOWN {time_since_last_seen}"
                else:
                    return "DOWN (unknown)"
            else:
                return "DOWN (unknown)"

    def _preformat_network_health_template_strings(self, health_metrics):
        """
        OPTIMIZATION: Pre-format all template strings to eliminate Jinja2 formatting overhead.
        
        Replaces dozens of template format operations like {{ "{:,}".format(...) }} and 
        {{ "%.1f%%"|format(...) }} with pre-computed Python strings. This provides 3-5x
        speedup since Jinja2 formatting goes through the template engine interpretation layer.
        
        Args:
            health_metrics (dict): Network health metrics dictionary to add formatted strings to
        """
        # Format all number values with comma separators (16+ format operations eliminated)
        integer_format_keys = [
            'relays_total', 'exit_count', 'guard_count', 'middle_count', 'authorities_count',
            'bad_exits_count', 'offline_relays', 'overloaded_relays',  # REMOVED: hibernating_relays
            # NEW: Additional flag counts
            'fast_count', 'stable_count', 'v2dir_count', 'hsdir_count', 'stabledesc_count', 'sybil_count',
            'new_relays_24h', 'new_relays_30d', 'new_relays_6m', 'new_relays_1y',
            'measured_relays', 'aroi_operators_count', 'relays_with_contact', 'relays_without_contact',
            'families_count', 'relays_with_family', 'relays_without_family', 'unique_contacts_count',
            'countries_count', 'unique_as_count', 'unique_platforms_count', 'platform_others',
            'recommended_version_count', 'not_recommended_count', 'experimental_count', 
            'obsolete_count', 'outdated_count', 'guard_exit_count', 'unrestricted_exits',
            'restricted_exits', 'web_traffic_exits', 'eu_relays_count', 'non_eu_relays_count',
            'rare_countries_relays', 'ipv4_only_relays', 'both_ipv4_ipv6_relays',
            # NEW: AROI domain-level metrics
            'unique_aroi_domains_count', 'validated_aroi_domains_count', 'invalid_aroi_domains_count',
            # NEW: IPv6 AROI operator metrics
            'ipv4_only_aroi_operators', 'both_ipv4_ipv6_aroi_operators'
        ]
        
        for key in integer_format_keys:
            if key in health_metrics:
                health_metrics[f'{key}_formatted'] = f"{health_metrics[key]:,}"
        
        # Format all percentage values with 1 decimal place (12+ format operations eliminated)
        percentage_format_keys = [
            'exit_percentage', 'guard_percentage', 'middle_percentage', 'authorities_percentage',
            'bad_exits_percentage', 'offline_relays_percentage', 'overloaded_relays_percentage',
            # REMOVED: 'hibernating_relays_percentage',
            # NEW: Additional flag percentages
            'fast_percentage', 'stable_percentage', 'v2dir_percentage', 'hsdir_percentage',
            'stabledesc_percentage', 'sybil_percentage',
            'new_relays_24h_percentage', 'new_relays_30d_percentage',
            'new_relays_6m_percentage', 'new_relays_1y_percentage', 'measured_percentage',
            'relays_with_contact_percentage', 'relays_without_contact_percentage',
            'relays_with_family_percentage', 'relays_without_family_percentage',
            'recommended_version_percentage', 'not_recommended_percentage', 'experimental_percentage',
            'obsolete_percentage', 'outdated_percentage', 'eu_consensus_weight_percentage',
            'non_eu_consensus_weight_percentage', 'rare_countries_consensus_weight_percentage',
            'eu_relays_percentage', 'non_eu_relays_percentage', 'rare_countries_relays_percentage',
            'top_3_as_concentration', 'top_5_as_concentration', 'top_10_as_concentration',
            # REFACTORED: Generate percentage format keys using consistent pattern
            'overall_uptime',
            'ipv4_only_relays_percentage', 'both_ipv4_ipv6_relays_percentage',
            'ipv4_only_bandwidth_percentage', 'both_ipv4_ipv6_bandwidth_percentage',
            # NEW: IPv6 AROI operator percentages
            'ipv4_only_aroi_operators_percentage', 'both_ipv4_ipv6_aroi_operators_percentage',
            # NEW: AROI domain percentages
            'validated_aroi_domains_percentage', 'invalid_aroi_domains_percentage'
        ]
        
        # Add 1_month period formatting keys (used directly in templates) 
        roles = ['exit', 'guard', 'middle', 'authority', 'v2dir', 'hsdir']
        statistics = ['mean', 'median']
        for role in roles:
            for stat in statistics:
                percentage_format_keys.append(f'{role}_uptime_1_month_{stat}')
        
        for key in percentage_format_keys:
            if key in health_metrics:
                health_metrics[f'{key}_formatted'] = f"{health_metrics[key]:.1f}%"
        
        # Format uptime time series data (4+ format operations eliminated)
        # Using consistent naming pattern: {role}_uptime_{period}_mean
        uptime_series_keys = [
            ('exit_uptime_1_month_mean', 'exit_uptime_6_months_mean', 'exit_uptime_1_year_mean', 'exit_uptime_5_years_mean'),
            ('guard_uptime_1_month_mean', 'guard_uptime_6_months_mean', 'guard_uptime_1_year_mean', 'guard_uptime_5_years_mean'),
            ('middle_uptime_1_month_mean', 'middle_uptime_6_months_mean', 'middle_uptime_1_year_mean', 'middle_uptime_5_years_mean'),
            ('authority_uptime_1_month_mean', 'authority_uptime_6_months_mean', 'authority_uptime_1_year_mean', 'authority_uptime_5_years_mean')
        ]
        
        for keys in uptime_series_keys:
            role = keys[0].split('_')[0]  # extract 'exit', 'guard', or 'middle'
            formatted_values = []
            for key in keys:
                if key in health_metrics:
                    formatted_values.append(f"{health_metrics[key]:.1f}%")
                else:
                    formatted_values.append("0.0%")
            health_metrics[f'{role}_uptime_series_formatted'] = " | ".join(formatted_values)
        
        # Format Top 3 AS data (loop with format operations eliminated)
        if 'top_3_as' in health_metrics:
            for as_info in health_metrics['top_3_as']:
                as_info['consensus_weight_percentage_formatted'] = f"{as_info['consensus_weight_percentage']:.1f}%"
        
        # Format Top 3 Countries data
        if 'top_3_countries' in health_metrics:
            for country_info in health_metrics['top_3_countries']:
                country_info['consensus_weight_percentage_formatted'] = f"{country_info['consensus_weight_percentage']:.1f}%"
        
        # Format platform data (loop with format operations eliminated)  
        if 'platform_top3' in health_metrics:
            formatted_platform_data = []
            for platform_data in health_metrics['platform_top3']:
                if len(platform_data) >= 3:  # (platform, count, percentage)
                    formatted_platform_data.append((
                        platform_data[0],  # platform name
                        f"{platform_data[1]:,}",  # formatted count
                        f"{platform_data[2]:.0f}%"  # formatted percentage
                    ))
                else:
                    formatted_platform_data.append(platform_data)
            health_metrics['platform_top3_formatted'] = formatted_platform_data
        
        # Format combined count + percentage strings (8+ format operations eliminated)
        combined_format_mappings = [
            ('exit_count', 'exit_percentage', 'exit_count_with_percentage'),
            ('guard_count', 'guard_percentage', 'guard_count_with_percentage'),
            ('middle_count', 'middle_percentage', 'middle_count_with_percentage'),
            ('authorities_count', 'authorities_percentage', 'authorities_count_with_percentage'),
            ('bad_exits_count', 'bad_exits_percentage', 'bad_exits_count_with_percentage'),
            # NEW: Additional flag count + percentage combinations
            ('fast_count', 'fast_percentage', 'fast_count_with_percentage'),
            ('stable_count', 'stable_percentage', 'stable_count_with_percentage'),
            ('v2dir_count', 'v2dir_percentage', 'v2dir_count_with_percentage'),
            ('hsdir_count', 'hsdir_percentage', 'hsdir_count_with_percentage'),
            ('stabledesc_count', 'stabledesc_percentage', 'stabledesc_count_with_percentage'),
            ('sybil_count', 'sybil_percentage', 'sybil_count_with_percentage'),
            ('offline_relays', 'offline_relays_percentage', 'offline_relays_with_percentage'),
            ('measured_relays', 'measured_percentage', 'measured_relays_with_percentage'),
            ('relays_with_contact', 'relays_with_contact_percentage', 'relays_with_contact_formatted')
        ]
        
        for count_key, pct_key, combined_key in combined_format_mappings:
            if count_key in health_metrics and pct_key in health_metrics:
                count_formatted = f"{health_metrics[count_key]:,}"
                pct_formatted = format_percentage_from_fraction(health_metrics[pct_key] / 100, 1, "0.0%")
                health_metrics[combined_key] = f"{count_formatted} ({pct_formatted})"

    def _calculate_network_health_metrics(self):
        """
        ULTRA-OPTIMIZED: Calculate network health metrics in single pass with maximum reuse.
        
        OPTIMIZATIONS APPLIED:
        1. Single loop through relays instead of 3 separate loops
        2. Reuse existing network_totals and sorted data 
        3. Pre-calculate all Jinja2 template values
        4. Consolidate uptime calculations for all periods
        5. Use existing data structures where possible
        """
        # Ensure prerequisites are available
        if 'network_totals' not in self.json:
            self._calculate_network_totals()
        if 'sorted' not in self.json:
            self._categorize()
        
        network_totals = self.json['network_totals']
        sorted_data = self.json['sorted']
        
        # REUSE EXISTING DATA - no recalculation needed
        total_relays_count = network_totals['total_relays']
        health_metrics = {
            'relays_total': total_relays_count,
            'guard_count': network_totals['guard_count'],
            'middle_count': network_totals['middle_count'], 
            'exit_count': network_totals['exit_count'],
            'measured_relays': network_totals['measured_relays'],
            'measured_percentage': network_totals['measured_percentage'],
            'countries_count': len(sorted_data.get('country', {})),
            'unique_as_count': len(sorted_data.get('as', {})),
            # Add percentages for relay counts
            'guard_percentage': (network_totals['guard_count'] / total_relays_count * 100) if total_relays_count > 0 else 0.0,
            'middle_percentage': (network_totals['middle_count'] / total_relays_count * 100) if total_relays_count > 0 else 0.0,
            'exit_percentage': (network_totals['exit_count'] / total_relays_count * 100) if total_relays_count > 0 else 0.0
        }
        
        # OPTIMIZED: Reuse cached unique families count from _calculate_and_cache_family_statistics()
        # This eliminates duplicate deduplication loops for better performance
        health_metrics['families_count'] = self.json.get('family_statistics', {}).get('unique_families_count', 0)
        
        # AROI operators - reuse existing calculation
        if hasattr(self, 'json') and 'aroi_leaderboards' in self.json:
            aroi_summary = self.json['aroi_leaderboards'].get('summary', {})
            health_metrics['aroi_operators_count'] = aroi_summary.get('total_operators', 0)
        else:
            health_metrics['aroi_operators_count'] = len(sorted_data.get('contact', {}))
        
        # Import modules once
        import statistics
        import datetime
        from .country_utils import is_eu_political, is_frontier_country
        from .uptime_utils import find_relay_uptime_data, calculate_relay_uptime_average
        
        # Time calculations for new relay detection - use centralized function
        time_thresholds = create_time_thresholds()
        now = time_thresholds['now']
        day_ago = time_thresholds['day_ago']
        month_ago = time_thresholds['month_ago']
        year_ago = time_thresholds['year_ago']
        six_months_ago = time_thresholds['six_months_ago']
        
        # Get rare countries once
        valid_rare_countries = set()
        try:
            if 'country' in sorted_data:
                from .country_utils import get_rare_countries_weighted_with_existing_data
                all_rare_countries = get_rare_countries_weighted_with_existing_data(
                    sorted_data['country'], network_totals['total_relays'])
                valid_rare_countries = {c.lower() for c in all_rare_countries if len(c) == 2 and c.isalpha()}
        except:
            pass
        
        # Initialize all counters and collectors for SINGLE LOOP
        authority_count = bad_exit_count = 0
        # NEW: Additional flag counts
        fast_count = stable_count = v2dir_count = hsdir_count = 0
        stabledesc_count = sybil_count = 0
        total_bandwidth = guard_bandwidth = exit_bandwidth = middle_bandwidth = 0
        # NEW: Additional flag-specific bandwidth collectors
        fast_bandwidth_values = []
        stable_bandwidth_values = []
        authority_bandwidth_values = []
        v2dir_bandwidth_values = []
        hsdir_bandwidth_values = []
        relays_with_family = relays_without_family = 0
        relays_with_contact = relays_without_contact = 0
        unique_contacts = set()
        eu_relays = non_eu_relays = rare_countries_relays = 0
        eu_consensus_weight = non_eu_consensus_weight = rare_countries_consensus_weight = 0
        offline_relays = overloaded_relays = 0  # REMOVED: hibernating_relays
        new_relays_24h = new_relays_30d = new_relays_1y = new_relays_6m = 0
        unique_platforms = set()
        platform_counts = {}
        recommended_version_count = not_recommended_count = 0
        experimental_count = obsolete_count = outdated_count = 0
        total_consensus_weight = total_advertised_bandwidth = 0
        observed_advertised_diff_sum = observed_advertised_count = 0
        observed_advertised_diff_values = []
        
        # NEW: Age calculations
        relay_ages_days = []
        
        # NEW: Exit policy analysis
        guard_exit_count = 0
        port_restricted_exits = 0
        port_unrestricted_exits = 0
        ip_unrestricted_exits = 0
        ip_restricted_exits = 0
        no_port_restrictions_and_no_ip_restrictions = 0  # NEW: Combined metric for both no port AND no IP restrictions
        web_traffic_exits = 0
        
        # Role-specific collectors - combined into single loop
        exit_cw_values = []
        guard_cw_values = []
        middle_cw_values = []
        exit_bw_values = []
        guard_bw_values = []
        middle_bw_values = []
        exit_cw_sum = exit_bw_sum = 0
        guard_cw_sum = guard_bw_sum = 0  
        middle_cw_sum = middle_bw_sum = 0
        
        # NEW: Geographic CW/BW ratio collectors
        eu_cw_bw_values = []
        non_eu_cw_bw_values = []
        
        # OPTIMIZATION: AS-specific CW/BW collectors (eliminates need for separate relay loop)
        as_cw_bw_data = {}  # as_number -> [cw_bw_ratios]
        
        # NEW: IPv6 support analysis - relay-level counters
        ipv4_only_relays = 0
        both_ipv4_ipv6_relays = 0
        
        # NEW: IPv6 support analysis - bandwidth-level counters
        ipv4_only_bandwidth = 0
        both_ipv4_ipv6_bandwidth = 0
        
        # NEW: IPv6 support analysis - country-level collections
        ipv4_only_countries = {}  # country -> count
        both_ipv4_ipv6_countries = {}  # country -> count
        
        # NEW: IPv6 support analysis - AS-level collections
        ipv4_only_as = {}  # as_number -> count
        both_ipv4_ipv6_as = {}  # as_number -> count
        
        # NEW: IPv6 support analysis - operator-level collections
        # Track what types of relays each operator has to determine their overall support
        operator_ipv6_status = {}  # domain -> {'has_ipv4_only': bool, 'has_dual_stack': bool}
        
        # Uptime data will be extracted from existing consolidated results after uptime API processing
        
        # SINGLE LOOP - calculate everything at once
        for relay in self.json['relays']:
            # Basic relay categorization
            flags = relay.get('flags', [])
            is_guard = 'Guard' in flags
            is_exit = 'Exit' in flags
            is_authority = 'Authority' in flags
            is_bad_exit = 'BadExit' in flags
            # NEW: Additional flag checks
            is_fast = 'Fast' in flags
            is_stable = 'Stable' in flags
            is_v2dir = 'V2Dir' in flags
            is_hsdir = 'HSDir' in flags
            is_stabledesc = 'StaleDesc' in flags
            is_sybil = 'Sybil' in flags
            is_running = relay.get('running', True)
            # REMOVED: is_hibernating
            is_overloaded = bool(relay.get('overload_general', False) or 
                                relay.get('overload_fd_exhausted', False) or 
                                relay.get('overload_write_limit', False) or 
                                relay.get('overload_read_limit', False))
            
            # Counts
            if is_authority:
                authority_count += 1
            if is_bad_exit:
                bad_exit_count += 1
            # NEW: Additional flag counts
            if is_fast:
                fast_count += 1
            if is_stable:
                stable_count += 1
            if is_v2dir:
                v2dir_count += 1
            if is_hsdir:
                hsdir_count += 1
            if is_stabledesc:
                stabledesc_count += 1
            if is_sybil:
                sybil_count += 1
            if not is_running:
                offline_relays += 1
            if is_overloaded:
                overloaded_relays += 1
            # REMOVED: hibernating count
            
            # NEW: Guard+Exit flag combination
            if is_guard and is_exit:
                guard_exit_count += 1
            
            # NEW: Exit policy analysis
            if is_exit:
                # Basic exit policy analysis
                exit_policy_summary = relay.get('exit_policy_summary', {})
                ipv4_summary = exit_policy_summary.get('accept', [])
                ipv6_summary = exit_policy_summary.get('accept6', [])
                
                # Check for web traffic (ports 80 and 443)
                has_web_traffic_ports = False
                if ipv4_summary:
                    for policy in ipv4_summary:
                        if ('80' in policy or '443' in policy or 
                            '1-65535' in policy or policy == '*:*'):
                            has_web_traffic_ports = True
                            break
                
                if has_web_traffic_ports:
                    web_traffic_exits += 1
                
                # Check for unrestricted exits (accept all or most traffic)
                is_port_unrestricted = False
                if ipv4_summary:
                    for policy in ipv4_summary:
                        if (policy == '*:*' or '1-65535' in policy or 
                            '1-' in policy or '*:1-65535' in policy):
                            is_port_unrestricted = True
                            break
                
                if is_port_unrestricted:
                    port_unrestricted_exits += 1
                else:
                    port_restricted_exits += 1
                
                # Check for IP address restrictions (excluding private/local IP ranges)
                # An exit relay has IP address restrictions only if it restricts public IP addresses
                # Restrictions on private/local IP ranges (192.168.x, 10.x, etc.) are not counted
                # as meaningful restrictions since they don't limit access to public internet resources
                has_ip_restrictions = False
                
                # Check full exit_policy for reject rules with public IP restrictions
                exit_policy = relay.get('exit_policy', [])
                for rule in exit_policy:
                    if rule.startswith('reject ') and ':' in rule:
                        # Extract IP part from "reject IP:PORT" rule using safe parsing
                        rule_part = rule[7:]  # Remove "reject "
                        if ':' in rule_part:
                            # Use safe IP parsing to extract IP part
                            parsed_ip, _ = _safe_parse_ip_address(rule_part)
                            # If it's a valid IP and not a private IP, it's a public IP restriction
                            if parsed_ip and not is_private_ip_address(parsed_ip):
                                has_ip_restrictions = True
                                break
                
                if has_ip_restrictions:
                    ip_restricted_exits += 1
                else:
                    ip_unrestricted_exits += 1
                
                # NEW: Track exits with BOTH no port restrictions AND no IP restrictions
                if is_port_unrestricted and not has_ip_restrictions:
                    no_port_restrictions_and_no_ip_restrictions += 1
            
            # NEW: Age calculation using first_seen - use centralized parsing
            first_seen_str = relay.get('first_seen', '')
            if first_seen_str:
                first_seen = parse_onionoo_timestamp(first_seen_str)
                if first_seen:
                    # Convert to naive datetime for comparison (since time_thresholds use naive datetimes)
                    first_seen_naive = first_seen.replace(tzinfo=None)
                    age_days = (now - first_seen_naive).days
                    if age_days >= 0:  # Sanity check
                        relay_ages_days.append(age_days)
                        
                        # Count new relays for existing metrics
                        if first_seen_naive >= day_ago:
                            new_relays_24h += 1
                        if first_seen_naive >= month_ago:
                            new_relays_30d += 1
                        if first_seen_naive >= year_ago:
                            new_relays_1y += 1
                        if first_seen_naive >= six_months_ago:
                            new_relays_6m += 1
            
            # Platform tracking
            platform = relay.get('platform', 'Unknown')
            unique_platforms.add(platform)
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
            
            # Version tracking
            recommended = relay.get('recommended_version')
            version_status = relay.get('version_status', '').lower()
            
            if recommended is True:
                recommended_version_count += 1
            elif recommended is False:
                not_recommended_count += 1
            
            if version_status == 'experimental':
                experimental_count += 1
            elif version_status == 'obsolete':
                obsolete_count += 1
            elif version_status in ['unrecommended', 'old']:
                outdated_count += 1
            
            # Bandwidth calculations
            bandwidth = relay.get('observed_bandwidth', 0)
            consensus_weight = relay.get('consensus_weight', 0)
            total_bandwidth += bandwidth
            advertised_bandwidth = relay.get('advertised_bandwidth', 0)
            total_consensus_weight += consensus_weight
            total_advertised_bandwidth += advertised_bandwidth
            
            if bandwidth > 0 and advertised_bandwidth > 0:
                diff = abs(bandwidth - advertised_bandwidth)
                observed_advertised_diff_sum += diff
                observed_advertised_count += 1
                observed_advertised_diff_values.append(diff)
            
            # Role-specific bandwidth and consensus weight - combined calculation
            if is_exit:
                exit_bandwidth += bandwidth
                if consensus_weight > 0 and bandwidth > 0:
                    exit_cw_sum += consensus_weight
                    exit_bw_sum += bandwidth
                    exit_cw_values.append(consensus_weight / bandwidth)
                    exit_bw_values.append(bandwidth)
            elif is_guard:
                guard_bandwidth += bandwidth
                if consensus_weight > 0 and bandwidth > 0:
                    guard_cw_sum += consensus_weight
                    guard_bw_sum += bandwidth
                    guard_cw_values.append(consensus_weight / bandwidth)
                    guard_bw_values.append(bandwidth)
            else:
                middle_bandwidth += bandwidth
                if consensus_weight > 0 and bandwidth > 0:
                    middle_cw_sum += consensus_weight
                    middle_bw_sum += bandwidth
                    middle_cw_values.append(consensus_weight / bandwidth)
                    middle_bw_values.append(bandwidth)
            
            # NEW: Flag-specific bandwidth collection for additional metrics
            if bandwidth > 0:  # Only collect bandwidth for relays with actual bandwidth
                if is_fast:
                    fast_bandwidth_values.append(bandwidth)
                if is_stable:
                    stable_bandwidth_values.append(bandwidth)
                if is_authority:
                    authority_bandwidth_values.append(bandwidth)
                if is_v2dir:
                    v2dir_bandwidth_values.append(bandwidth)
                if is_hsdir:
                    hsdir_bandwidth_values.append(bandwidth)
            
            # Family and contact info
            effective_family = relay.get('effective_family', [])
            if effective_family and len(effective_family) > 1:
                relays_with_family += 1
            else:
                relays_without_family += 1
            
            contact = relay.get('contact', '').strip()
            unique_contacts.add(contact)
            if contact:
                relays_with_contact += 1
            else:
                relays_without_contact += 1
            
            # Geographic data - relay["country"] already UPPERCASE from _preprocess_template_data()
            country = relay.get('country', '')
            if country and len(country) == 2:
                if is_eu_political(country):
                    eu_relays += 1
                    eu_consensus_weight += consensus_weight
                    # NEW: Collect EU CW/BW ratios for mean/median calculation
                    if consensus_weight > 0 and bandwidth > 0:
                        eu_cw_bw_values.append(consensus_weight / bandwidth * 1000000)
                else:
                    non_eu_relays += 1
                    non_eu_consensus_weight += consensus_weight
                    # NEW: Collect Non-EU CW/BW ratios for mean/median calculation
                    if consensus_weight > 0 and bandwidth > 0:
                        non_eu_cw_bw_values.append(consensus_weight / bandwidth * 1000000)
                
                if country.lower() in valid_rare_countries or (not valid_rare_countries and is_frontier_country(country)):
                    rare_countries_relays += 1
                    rare_countries_consensus_weight += consensus_weight
                    
            # OPTIMIZATION: AS-specific CW/BW collection (eliminates separate loop)
            as_number = relay.get('as')
            if as_number and consensus_weight > 0 and bandwidth > 0:
                cw_bw_ratio = consensus_weight / bandwidth * 1000000
                if as_number not in as_cw_bw_data:
                    as_cw_bw_data[as_number] = []
                as_cw_bw_data[as_number].append(cw_bw_ratio)
            
            # NEW: IPv6 support analysis - determine IP version support for this relay
            or_addresses = relay.get('or_addresses', [])
            ipv6_support = determine_ipv6_support(or_addresses)
            
            # Count relay-level IPv6 support
            if ipv6_support == 'ipv4_only':
                ipv4_only_relays += 1
                ipv4_only_bandwidth += bandwidth
            elif ipv6_support == 'both':
                both_ipv4_ipv6_relays += 1
                both_ipv4_ipv6_bandwidth += bandwidth
            
            # Country-level IPv6 support tracking
            if country and len(country) == 2:
                if ipv6_support == 'ipv4_only':
                    ipv4_only_countries[country] = ipv4_only_countries.get(country, 0) + 1
                elif ipv6_support == 'both':
                    both_ipv4_ipv6_countries[country] = both_ipv4_ipv6_countries.get(country, 0) + 1
            
            # AS-level IPv6 support tracking
            if as_number:
                if ipv6_support == 'ipv4_only':
                    ipv4_only_as[as_number] = ipv4_only_as.get(as_number, 0) + 1
                elif ipv6_support == 'both':
                    both_ipv4_ipv6_as[as_number] = both_ipv4_ipv6_as.get(as_number, 0) + 1
            
            # Operator-level IPv6 support tracking (uses AROI domain for consistency with Option B)
            aroi_domain = relay.get('aroi_domain', 'none')
            if aroi_domain and aroi_domain != 'none':
                if aroi_domain not in operator_ipv6_status:
                    operator_ipv6_status[aroi_domain] = {'has_ipv4_only': False, 'has_dual_stack': False}
                
                if ipv6_support == 'ipv4_only':
                    operator_ipv6_status[aroi_domain]['has_ipv4_only'] = True
                elif ipv6_support == 'both':
                    operator_ipv6_status[aroi_domain]['has_dual_stack'] = True
            
            # Skip uptime calculation here - will use existing consolidated results
        
        # NEW: Calculate age statistics
            # Skip uptime calculation here - will use existing consolidated results
        
        # NEW: Calculate age statistics
        def _format_age(days):
            """Format age in days to 'Xy Zmo' format"""
            if days < 30:
                return f"{days}d"
            elif days < 365:
                months = days // 30
                remaining_days = days % 30
                if remaining_days == 0:
                    return f"{months}mo"
                else:
                    return f"{months}mo {remaining_days}d"
            else:
                years = days // 365
                remaining_days = days % 365
                months = remaining_days // 30
                if months == 0:
                    return f"{years}y"
                else:
                    return f"{years}y {months}mo"
        
        if relay_ages_days:
            mean_age_days = statistics.mean(relay_ages_days)
            median_age_days = statistics.median(relay_ages_days)
            health_metrics['network_mean_age_formatted'] = _format_age(int(mean_age_days))
            health_metrics['network_median_age_formatted'] = _format_age(int(median_age_days))
        else:
            health_metrics['network_mean_age_formatted'] = "Unknown"
            health_metrics['network_median_age_formatted'] = "Unknown"
        
        # NEW: Top 3 countries by consensus weight (reuse existing sorted data)
        # Country keys are already UPPERCASE
        countries_by_cw = []
        if 'country' in sorted_data:
            for country_code, country_data in sorted_data['country'].items():
                if len(country_code) == 2:  # Valid country code
                    cw_fraction = country_data.get('consensus_weight_fraction', 0)
                    if cw_fraction > 0:
                        countries_by_cw.append((country_code, cw_fraction))
        
        countries_by_cw.sort(key=lambda x: x[1], reverse=True)
        health_metrics['top_3_countries'] = []
        for i, (country_code, cw_fraction) in enumerate(countries_by_cw[:3]):
            health_metrics['top_3_countries'].append({
                'rank': i + 1,
                'country_code': country_code,
                'consensus_weight_percentage': cw_fraction * 100
            })
        
        # NEW: Top AS by consensus weight and concentration metrics
        as_by_cw = []
        if 'as' in sorted_data:
            for as_number, as_data in sorted_data['as'].items():
                cw_fraction = as_data.get('consensus_weight_fraction', 0)
                if cw_fraction > 0:
                    as_name = as_data.get('as_name', f'AS{as_number}')
                    as_by_cw.append((as_number, as_name, cw_fraction))
        
        as_by_cw.sort(key=lambda x: x[2], reverse=True)
        
        # Top 3 AS details
        health_metrics['top_3_as'] = []
        for i, (as_number, as_name, cw_fraction) in enumerate(as_by_cw[:3]):
            health_metrics['top_3_as'].append({
                'rank': i + 1,
                'as_number': as_number,
                'as_name': as_name,
                'as_name_truncated': as_name[:8] if as_name and len(as_name) > 8 else (as_name or f'AS{as_number}'),
                'consensus_weight_percentage': cw_fraction * 100
            })
        
        # AS concentration metrics
        if as_by_cw:
            top_3_cw = sum(x[2] for x in as_by_cw[:3])
            top_5_cw = sum(x[2] for x in as_by_cw[:5])
            top_10_cw = sum(x[2] for x in as_by_cw[:10])
            
            health_metrics['top_3_as_concentration'] = top_3_cw * 100
            health_metrics['top_5_as_concentration'] = top_5_cw * 100
            health_metrics['top_10_as_concentration'] = top_10_cw * 100
        else:
            health_metrics['top_3_as_concentration'] = 0.0
            health_metrics['top_5_as_concentration'] = 0.0
            health_metrics['top_10_as_concentration'] = 0.0
        
        # NEW: Calculate geographic CW/BW ratios (mean and median)
        health_metrics.update({
            'eu_cw_bw_mean': int(statistics.mean(eu_cw_bw_values)) if eu_cw_bw_values else 0,
            'eu_cw_bw_median': int(statistics.median(eu_cw_bw_values)) if eu_cw_bw_values else 0,
            'non_eu_cw_bw_mean': int(statistics.mean(non_eu_cw_bw_values)) if non_eu_cw_bw_values else 0,
            'non_eu_cw_bw_median': int(statistics.median(non_eu_cw_bw_values)) if non_eu_cw_bw_values else 0
        })
        
        # OPTIMIZATION: Extract Top AS CW/BW values from collected data (eliminates extra loop)
        # Extract data for top ASes using the as_cw_bw_data collected in the main relay loop above
        top_3_as_cw_bw_values = []
        top_5_as_cw_bw_values = []
        top_10_as_cw_bw_values = []
        
        if as_by_cw:
            # Get AS numbers for top ASes
            top_3_as_numbers = {x[0] for x in as_by_cw[:3]}
            top_5_as_numbers = {x[0] for x in as_by_cw[:5]}
            top_10_as_numbers = {x[0] for x in as_by_cw[:10]}
            
            # Extract CW/BW ratios from collected data
            for as_number, cw_bw_ratios in as_cw_bw_data.items():
                if as_number in top_3_as_numbers:
                    top_3_as_cw_bw_values.extend(cw_bw_ratios)
                if as_number in top_5_as_numbers:
                    top_5_as_cw_bw_values.extend(cw_bw_ratios)
                if as_number in top_10_as_numbers:
                    top_10_as_cw_bw_values.extend(cw_bw_ratios)
        
        health_metrics.update({
            'top_3_as_cw_bw_mean': int(statistics.mean(top_3_as_cw_bw_values)) if top_3_as_cw_bw_values else 0,
            'top_3_as_cw_bw_median': int(statistics.median(top_3_as_cw_bw_values)) if top_3_as_cw_bw_values else 0,
            'top_5_as_cw_bw_mean': int(statistics.mean(top_5_as_cw_bw_values)) if top_5_as_cw_bw_values else 0,
            'top_5_as_cw_bw_median': int(statistics.median(top_5_as_cw_bw_values)) if top_5_as_cw_bw_values else 0,
            'top_10_as_cw_bw_mean': int(statistics.mean(top_10_as_cw_bw_values)) if top_10_as_cw_bw_values else 0,
            'top_10_as_cw_bw_median': int(statistics.median(top_10_as_cw_bw_values)) if top_10_as_cw_bw_values else 0
        })
        
        # NEW: Exit policy metrics (FIXED: use exit_count for percentage calculations)
        exit_count = network_totals['exit_count']
        health_metrics.update({
            'guard_exit_count': guard_exit_count,
            'unrestricted_exits': port_unrestricted_exits,
            'restricted_exits': port_restricted_exits,
            'web_traffic_exits': web_traffic_exits,
            'ip_unrestricted_exits': ip_unrestricted_exits,
            'ip_restricted_exits': ip_restricted_exits,
            'unrestricted_and_no_ip_restrictions': no_port_restrictions_and_no_ip_restrictions,  # NEW: Combined metric
            # FIXED: Port restriction percentages use total_relays_count (applies to all relays)
            'unrestricted_exits_percentage': (port_unrestricted_exits / exit_count * 100) if exit_count > 0 else 0.0,
            'restricted_exits_percentage': (port_restricted_exits / exit_count * 100) if exit_count > 0 else 0.0,
            'web_traffic_exits_percentage': (web_traffic_exits / exit_count * 100) if exit_count > 0 else 0.0,
            'guard_exit_percentage': (guard_exit_count / total_relays_count * 100) if total_relays_count > 0 else 0.0,
            # FIXED: IP restriction percentages use exit_count (applies only to exit relays)
            'ip_unrestricted_exits_percentage': (ip_unrestricted_exits / exit_count * 100) if exit_count > 0 else 0.0,
            'ip_restricted_exits_percentage': (ip_restricted_exits / exit_count * 100) if exit_count > 0 else 0.0,
            'unrestricted_and_no_ip_restrictions_percentage': (no_port_restrictions_and_no_ip_restrictions / exit_count * 100) if exit_count > 0 else 0.0
        })
        
        # STORE CALCULATED METRICS
        health_metrics.update({
            'authorities_count': authority_count,
            'bad_exits_count': bad_exit_count,
            # NEW: Additional flag counts
            'fast_count': fast_count,
            'stable_count': stable_count,
            'v2dir_count': v2dir_count,
            'hsdir_count': hsdir_count,
            'stabledesc_count': stabledesc_count,
            'sybil_count': sybil_count,
            'offline_relays': offline_relays,
            'overloaded_relays': overloaded_relays,
            # REMOVED: 'hibernating_relays': hibernating_relays,
            'new_relays_24h': new_relays_24h,
            'new_relays_30d': new_relays_30d,
            'new_relays_1y': new_relays_1y,
            'new_relays_6m': new_relays_6m,
            'unique_platforms_count': len(unique_platforms),
            'unique_contacts_count': len(unique_contacts),
            'relays_with_family': relays_with_family,
            'relays_without_family': relays_without_family,
            'relays_with_contact': relays_with_contact,
            'relays_without_contact': relays_without_contact,
            'eu_relays_count': eu_relays,
            'non_eu_relays_count': non_eu_relays,
            'rare_countries_relays': rare_countries_relays,
            'eu_relays_percentage': (eu_relays / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'non_eu_relays_percentage': (non_eu_relays / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'rare_countries_relays_percentage': (rare_countries_relays / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            # Geographic consensus weight metrics
            'eu_consensus_weight': eu_consensus_weight,
            'non_eu_consensus_weight': non_eu_consensus_weight,
            'rare_countries_consensus_weight': rare_countries_consensus_weight,
            'eu_consensus_weight_percentage': (eu_consensus_weight / total_consensus_weight * 100) if total_consensus_weight > 0 else 0.0,
            'non_eu_consensus_weight_percentage': (non_eu_consensus_weight / total_consensus_weight * 100) if total_consensus_weight > 0 else 0.0,
            'rare_countries_consensus_weight_percentage': (rare_countries_consensus_weight / total_consensus_weight * 100) if total_consensus_weight > 0 else 0.0,
            # Geographic analysis metrics from intelligence engine
            'geographic_diversity_top3': self.json.get('smart_context', {}).get('concentration_patterns', {}).get('template_optimized', {}).get('countries_top_3_percentage', '0.0'),
            'geographic_diversity_significant_count': self.json.get('smart_context', {}).get('concentration_patterns', {}).get('template_optimized', {}).get('countries_significant_count', 0),
            'geographic_diversity_five_eyes': self.json.get('smart_context', {}).get('concentration_patterns', {}).get('template_optimized', {}).get('countries_five_eyes_percentage', '0.0'),
            'jurisdiction_five_eyes': self.json.get('smart_context', {}).get('geographic_clustering', {}).get('template_optimized', {}).get('five_eyes_influence', '0.0'),
            'jurisdiction_fourteen_eyes': self.json.get('smart_context', {}).get('geographic_clustering', {}).get('template_optimized', {}).get('fourteen_eyes_influence', '0.0'),
            'regional_concentration_level': self.json.get('smart_context', {}).get('geographic_clustering', {}).get('template_optimized', {}).get('concentration_hhi_interpretation', 'UNKNOWN'),
            'regional_hhi': self.json.get('smart_context', {}).get('geographic_clustering', {}).get('template_optimized', {}).get('regional_hhi', '0.000'),
            'regional_top_3_breakdown': self.json.get('smart_context', {}).get('geographic_clustering', {}).get('template_optimized', {}).get('top_3_regions', 'Insufficient data'),
            # Add percentages for other relay counts
            'authorities_percentage': (authority_count / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'bad_exits_percentage': (bad_exit_count / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            # NEW: Additional flag percentages
            'fast_percentage': (fast_count / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'stable_percentage': (stable_count / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'v2dir_percentage': (v2dir_count / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'hsdir_percentage': (hsdir_count / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'stabledesc_percentage': (stabledesc_count / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'sybil_percentage': (sybil_count / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'offline_relays_percentage': (offline_relays / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'overloaded_relays_percentage': (overloaded_relays / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            # REMOVED: 'hibernating_relays_percentage': (hibernating_relays / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'new_relays_24h_percentage': (new_relays_24h / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'new_relays_30d_percentage': (new_relays_30d / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'new_relays_1y_percentage': (new_relays_1y / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0,
            'new_relays_6m_percentage': (new_relays_6m / health_metrics['relays_total'] * 100) if health_metrics['relays_total'] > 0 else 0.0
        })
        
        # NEW: IPv6 support metrics - relay-level statistics
        health_metrics.update({
            'ipv4_only_relays': ipv4_only_relays,
            'both_ipv4_ipv6_relays': both_ipv4_ipv6_relays,
            'ipv4_only_relays_percentage': (ipv4_only_relays / total_relays_count * 100) if total_relays_count > 0 else 0.0,
            'both_ipv4_ipv6_relays_percentage': (both_ipv4_ipv6_relays / total_relays_count * 100) if total_relays_count > 0 else 0.0
        })
        
        # NEW: IPv6 support metrics - bandwidth-level statistics
        health_metrics.update({
            'ipv4_only_bandwidth': ipv4_only_bandwidth,
            'both_ipv4_ipv6_bandwidth': both_ipv4_ipv6_bandwidth,
            'ipv4_only_bandwidth_percentage': (ipv4_only_bandwidth / total_bandwidth * 100) if total_bandwidth > 0 else 0.0,
            'both_ipv4_ipv6_bandwidth_percentage': (both_ipv4_ipv6_bandwidth / total_bandwidth * 100) if total_bandwidth > 0 else 0.0
        })
        
        # NEW: IPv6 support metrics - operator-level statistics (counts only, percentages calculated later)
        # Note: These counts will be recalculated after AROI validation to only include validated operators
        # Temporarily store the full operator_ipv6_status dict for later filtering
        health_metrics['_temp_operator_ipv6_status'] = operator_ipv6_status
        
        # NEW: IPv6 support metrics - top country analysis
        # Find top country for each IPv6 category
        top_ipv4_only_country = max(ipv4_only_countries.items(), key=lambda x: x[1]) if ipv4_only_countries else ('N/A', 0)
        top_both_country = max(both_ipv4_ipv6_countries.items(), key=lambda x: x[1]) if both_ipv4_ipv6_countries else ('N/A', 0)
        
        health_metrics.update({
            'top_ipv4_only_country': top_ipv4_only_country[0],
            'top_ipv4_only_country_count': top_ipv4_only_country[1],
            'top_ipv4_only_country_percentage': (top_ipv4_only_country[1] / total_relays_count * 100) if total_relays_count > 0 else 0.0,
            'top_both_ipv4_ipv6_country': top_both_country[0],
            'top_both_ipv4_ipv6_country_count': top_both_country[1],
            'top_both_ipv4_ipv6_country_percentage': (top_both_country[1] / total_relays_count * 100) if total_relays_count > 0 else 0.0
        })
        
        # NEW: IPv6 support metrics - top AS analysis
        # Find top AS for each IPv6 category
        top_ipv4_only_as = max(ipv4_only_as.items(), key=lambda x: x[1]) if ipv4_only_as else (None, 0)
        top_both_as = max(both_ipv4_ipv6_as.items(), key=lambda x: x[1]) if both_ipv4_ipv6_as else (None, 0)
        
        # Get AS names from sorted data
        as_names = {}
        if 'as' in sorted_data:
            for as_number, as_data in sorted_data['as'].items():
                as_names[as_number] = as_data.get('as_name', f'AS{as_number}')
        
        health_metrics.update({
            'top_ipv4_only_as_number': top_ipv4_only_as[0],
            'top_ipv4_only_as_name': as_names.get(top_ipv4_only_as[0], 'Unknown') if top_ipv4_only_as[0] else 'N/A',
            'top_ipv4_only_as_count': top_ipv4_only_as[1],
            'top_ipv4_only_as_percentage': (top_ipv4_only_as[1] / total_relays_count * 100) if total_relays_count > 0 else 0.0,
            'top_both_ipv4_ipv6_as_number': top_both_as[0],
            'top_both_ipv4_ipv6_as_name': as_names.get(top_both_as[0], 'Unknown') if top_both_as[0] else 'N/A',
            'top_both_ipv4_ipv6_as_count': top_both_as[1],
            'top_both_ipv4_ipv6_as_percentage': (top_both_as[1] / total_relays_count * 100) if total_relays_count > 0 else 0.0
        })
        
        # Platform metrics with percentages
        total_relays = health_metrics['relays_total']
        sorted_platforms = sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)
        top_platforms = sorted_platforms[:3]
        others_count = sum(count for _, count in sorted_platforms[3:])
        
        top_platforms_with_pct = []
        for platform, count in top_platforms:
            percentage = (count / total_relays * 100) if total_relays > 0 else 0.0
            top_platforms_with_pct.append((platform, count, percentage))
        
        health_metrics['platform_top3'] = top_platforms_with_pct
        health_metrics['platform_others'] = others_count
        health_metrics['platform_others_percentage'] = (others_count / total_relays * 100) if total_relays > 0 else 0.0
        
        # Version compliance with percentages
        total_with_version_info = recommended_version_count + not_recommended_count
        health_metrics.update({
            'recommended_version_percentage': (
                (recommended_version_count / total_with_version_info * 100) 
                if total_with_version_info > 0 else 0.0
            ),
            'recommended_version_count': recommended_version_count,
            'not_recommended_count': not_recommended_count,
            'experimental_count': experimental_count,
            'obsolete_count': obsolete_count,
            'outdated_count': outdated_count,
            'not_recommended_percentage': (not_recommended_count / total_relays * 100) if total_relays > 0 else 0.0,
            'experimental_percentage': (experimental_count / total_relays * 100) if total_relays > 0 else 0.0,
            'obsolete_percentage': (obsolete_count / total_relays * 100) if total_relays > 0 else 0.0,
            'outdated_percentage': (outdated_count / total_relays * 100) if total_relays > 0 else 0.0
        })
        
        # Bandwidth utilization metrics - calculate mean and median for Obs to Adv Diff
        avg_obs_adv_diff_bytes = (
            (observed_advertised_diff_sum / observed_advertised_count) 
            if observed_advertised_count > 0 else 0
        )
        median_obs_adv_diff_bytes = (
            statistics.median(observed_advertised_diff_values)
            if observed_advertised_diff_values else 0
        )
        
        if self.use_bits:
            obs_adv_unit = self.bandwidth_formatter.determine_unit(avg_obs_adv_diff_bytes * 8)
            avg_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(avg_obs_adv_diff_bytes * 8, obs_adv_unit, decimal_places=0) + f" {obs_adv_unit}"
            median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(median_obs_adv_diff_bytes * 8, obs_adv_unit, decimal_places=0) + f" {obs_adv_unit}"
            health_metrics['avg_observed_advertised_diff_formatted'] = f"{avg_formatted} | {median_formatted}"
        else:
            obs_adv_unit = self.bandwidth_formatter.determine_unit(avg_obs_adv_diff_bytes)
            avg_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(avg_obs_adv_diff_bytes, obs_adv_unit, decimal_places=0) + f" {obs_adv_unit}"
            median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(median_obs_adv_diff_bytes, obs_adv_unit, decimal_places=0) + f" {obs_adv_unit}"
            health_metrics['avg_observed_advertised_diff_formatted'] = f"{avg_formatted} | {median_formatted}"
        
        health_metrics['consensus_weight_bandwidth_ratio'] = (
            (total_consensus_weight / total_bandwidth) 
            if total_bandwidth > 0 else 0.0
        )
        
        # Role-specific CW/BW ratios and bandwidth statistics
        health_metrics.update({
            'exit_cw_bw_overall': (exit_cw_sum / exit_bw_sum) if exit_bw_sum > 0 else 0.0,
            'guard_cw_bw_overall': (guard_cw_sum / guard_bw_sum) if guard_bw_sum > 0 else 0.0,
            'middle_cw_bw_overall': (middle_cw_sum / middle_bw_sum) if middle_bw_sum > 0 else 0.0,
            'exit_cw_bw_avg': statistics.mean(exit_cw_values) if exit_cw_values else 0.0,
            'guard_cw_bw_avg': statistics.mean(guard_cw_values) if guard_cw_values else 0.0,
            'middle_cw_bw_avg': statistics.mean(middle_cw_values) if middle_cw_values else 0.0,
            'exit_cw_bw_median': statistics.median(exit_cw_values) if exit_cw_values else 0.0,
            'guard_cw_bw_median': statistics.median(guard_cw_values) if guard_cw_values else 0.0,
            'middle_cw_bw_median': statistics.median(middle_cw_values) if middle_cw_values else 0.0,
            'exit_bw_mean': statistics.mean(exit_bw_values) if exit_bw_values else 0.0,
            'guard_bw_mean': statistics.mean(guard_bw_values) if guard_bw_values else 0.0,
            'middle_bw_mean': statistics.mean(middle_bw_values) if middle_bw_values else 0.0,
            'exit_bw_median': statistics.median(exit_bw_values) if exit_bw_values else 0.0,
            'guard_bw_median': statistics.median(guard_bw_values) if guard_bw_values else 0.0,
            'middle_bw_median': statistics.median(middle_bw_values) if middle_bw_values else 0.0,
            # NEW: Flag-specific bandwidth statistics
            'fast_bw_mean': statistics.mean(fast_bandwidth_values) if fast_bandwidth_values else 0.0,
            'fast_bw_median': statistics.median(fast_bandwidth_values) if fast_bandwidth_values else 0.0,
            'stable_bw_mean': statistics.mean(stable_bandwidth_values) if stable_bandwidth_values else 0.0,
            'stable_bw_median': statistics.median(stable_bandwidth_values) if stable_bandwidth_values else 0.0,
            'authority_bw_mean': statistics.mean(authority_bandwidth_values) if authority_bandwidth_values else 0.0,
            'authority_bw_median': statistics.median(authority_bandwidth_values) if authority_bandwidth_values else 0.0,
            'v2dir_bw_mean': statistics.mean(v2dir_bandwidth_values) if v2dir_bandwidth_values else 0.0,
            'v2dir_bw_median': statistics.median(v2dir_bandwidth_values) if v2dir_bandwidth_values else 0.0,
            'hsdir_bw_mean': statistics.mean(hsdir_bandwidth_values) if hsdir_bandwidth_values else 0.0,
            'hsdir_bw_median': statistics.median(hsdir_bandwidth_values) if hsdir_bandwidth_values else 0.0
        })
        
        # PRE-CALCULATE BANDWIDTH MEAN/MEDIAN WITH PROPER UNITS - avoid showing 0 values
        # Check if any mean/median would show as 0 with the main unit, if so use smaller unit for all
        if self.use_bits:
            # For bits, check if any value would round to 0 with Gbit/s
            base_unit = self.bandwidth_formatter.determine_unit(total_bandwidth * 8)
            test_values = [
                health_metrics['exit_bw_mean'] * 8,
                health_metrics['exit_bw_median'] * 8,
                health_metrics['guard_bw_mean'] * 8,
                health_metrics['guard_bw_median'] * 8,
                health_metrics['middle_bw_mean'] * 8,
                health_metrics['middle_bw_median'] * 8
            ]
            
            # Check if any would format to 0 with the base unit
            use_smaller_unit = False
            for value in test_values:
                if value > 0:  # Only check non-zero values
                    formatted_val = self.bandwidth_formatter.format_bandwidth_with_unit(value, base_unit, decimal_places=0)
                    if float(formatted_val) == 0:
                        use_smaller_unit = True
                        break
            
            # Use Mbit/s if any would show as 0 Gbit/s
            unit = 'Mbit/s' if (use_smaller_unit and base_unit == 'Gbit/s') else base_unit
            
            exit_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['exit_bw_mean'] * 8, unit, decimal_places=0) + f" {unit}"
            exit_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['exit_bw_median'] * 8, unit, decimal_places=0) + f" {unit}"
            guard_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['guard_bw_mean'] * 8, unit, decimal_places=0) + f" {unit}"
            guard_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['guard_bw_median'] * 8, unit, decimal_places=0) + f" {unit}"
            middle_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['middle_bw_mean'] * 8, unit, decimal_places=0) + f" {unit}"
            middle_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['middle_bw_median'] * 8, unit, decimal_places=0) + f" {unit}"
            # NEW: Additional flag-specific bandwidth formatting
            fast_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['fast_bw_mean'] * 8, unit, decimal_places=0) + f" {unit}"
            fast_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['fast_bw_median'] * 8, unit, decimal_places=0) + f" {unit}"
            stable_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['stable_bw_mean'] * 8, unit, decimal_places=0) + f" {unit}"
            stable_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['stable_bw_median'] * 8, unit, decimal_places=0) + f" {unit}"
            authority_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['authority_bw_mean'] * 8, unit, decimal_places=0) + f" {unit}"
            authority_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['authority_bw_median'] * 8, unit, decimal_places=0) + f" {unit}"
            v2dir_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['v2dir_bw_mean'] * 8, unit, decimal_places=0) + f" {unit}"
            v2dir_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['v2dir_bw_median'] * 8, unit, decimal_places=0) + f" {unit}"
            hsdir_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['hsdir_bw_mean'] * 8, unit, decimal_places=0) + f" {unit}"
            hsdir_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['hsdir_bw_median'] * 8, unit, decimal_places=0) + f" {unit}"
        else:
            # For bytes, check if any value would round to 0 with GB/s
            base_unit = self.bandwidth_formatter.determine_unit(total_bandwidth)
            test_values = [
                health_metrics['exit_bw_mean'],
                health_metrics['exit_bw_median'],
                health_metrics['guard_bw_mean'],
                health_metrics['guard_bw_median'],
                health_metrics['middle_bw_mean'],
                health_metrics['middle_bw_median']
            ]
            
            # Check if any would format to 0 with the base unit
            use_smaller_unit = False
            for value in test_values:
                if value > 0:  # Only check non-zero values
                    formatted_val = self.bandwidth_formatter.format_bandwidth_with_unit(value, base_unit, decimal_places=0)
                    if float(formatted_val) == 0:
                        use_smaller_unit = True
                        break
            
            # Use MB/s if any would show as 0 GB/s
            unit = 'MB/s' if (use_smaller_unit and base_unit == 'GB/s') else base_unit
            
            exit_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['exit_bw_mean'], unit, decimal_places=0) + f" {unit}"
            exit_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['exit_bw_median'], unit, decimal_places=0) + f" {unit}"
            guard_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['guard_bw_mean'], unit, decimal_places=0) + f" {unit}"
            guard_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['guard_bw_median'], unit, decimal_places=0) + f" {unit}"
            middle_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['middle_bw_mean'], unit, decimal_places=0) + f" {unit}"
            middle_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['middle_bw_median'], unit, decimal_places=0) + f" {unit}"
            # NEW: Additional flag-specific bandwidth formatting (bytes)
            fast_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['fast_bw_mean'], unit, decimal_places=0) + f" {unit}"
            fast_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['fast_bw_median'], unit, decimal_places=0) + f" {unit}"
            stable_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['stable_bw_mean'], unit, decimal_places=0) + f" {unit}"
            stable_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['stable_bw_median'], unit, decimal_places=0) + f" {unit}"
            authority_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['authority_bw_mean'], unit, decimal_places=0) + f" {unit}"
            authority_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['authority_bw_median'], unit, decimal_places=0) + f" {unit}"
            v2dir_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['v2dir_bw_mean'], unit, decimal_places=0) + f" {unit}"
            v2dir_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['v2dir_bw_median'], unit, decimal_places=0) + f" {unit}"
            hsdir_mean_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['hsdir_bw_mean'], unit, decimal_places=0) + f" {unit}"
            hsdir_median_formatted = self.bandwidth_formatter.format_bandwidth_with_unit(health_metrics['hsdir_bw_median'], unit, decimal_places=0) + f" {unit}"
        
        health_metrics.update({
            'exit_bw_mean_formatted': exit_mean_formatted,
            'exit_bw_median_formatted': exit_median_formatted,
            'guard_bw_mean_formatted': guard_mean_formatted,
            'guard_bw_median_formatted': guard_median_formatted,
            'middle_bw_mean_formatted': middle_mean_formatted,
            'middle_bw_median_formatted': middle_median_formatted,
            # NEW: Additional flag-specific bandwidth formatted values
            'fast_bw_mean_formatted': fast_mean_formatted,
            'fast_bw_median_formatted': fast_median_formatted,
            'stable_bw_mean_formatted': stable_mean_formatted,
            'stable_bw_median_formatted': stable_median_formatted,
            'authority_bw_mean_formatted': authority_mean_formatted,
            'authority_bw_median_formatted': authority_median_formatted,
            'v2dir_bw_mean_formatted': v2dir_mean_formatted,
            'v2dir_bw_median_formatted': v2dir_median_formatted,
            'hsdir_bw_mean_formatted': hsdir_mean_formatted,
            'hsdir_bw_median_formatted': hsdir_median_formatted
        })
        
        # Bandwidth formatting with proper units
        if self.use_bits:
            unit = self.bandwidth_formatter.determine_unit(total_bandwidth * 8)
            health_metrics['total_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(total_bandwidth * 8, unit, decimal_places=0) + f" {unit}"
            health_metrics['guard_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(guard_bandwidth * 8, unit, decimal_places=0) + f" {unit}"
            health_metrics['exit_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(exit_bandwidth * 8, unit, decimal_places=0) + f" {unit}"
            health_metrics['middle_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(middle_bandwidth * 8, unit, decimal_places=0) + f" {unit}"
            # NEW: IPv6 bandwidth formatting (bits)
            health_metrics['ipv4_only_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(ipv4_only_bandwidth * 8, unit, decimal_places=0) + f" {unit}"
            health_metrics['both_ipv4_ipv6_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(both_ipv4_ipv6_bandwidth * 8, unit, decimal_places=0) + f" {unit}"
        else:
            unit = self.bandwidth_formatter.determine_unit(total_bandwidth)
            health_metrics['total_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(total_bandwidth, unit, decimal_places=0) + f" {unit}"
            health_metrics['guard_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(guard_bandwidth, unit, decimal_places=0) + f" {unit}"
            health_metrics['exit_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(exit_bandwidth, unit, decimal_places=0) + f" {unit}"
            health_metrics['middle_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(middle_bandwidth, unit, decimal_places=0) + f" {unit}"
            # NEW: IPv6 bandwidth formatting (bytes)
            health_metrics['ipv4_only_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(ipv4_only_bandwidth, unit, decimal_places=0) + f" {unit}"
            health_metrics['both_ipv4_ipv6_bandwidth_formatted'] = self.bandwidth_formatter.format_bandwidth_with_unit(both_ipv4_ipv6_bandwidth, unit, decimal_places=0) + f" {unit}"
        
        # Uptime metrics - reuse existing consolidated uptime calculations for efficiency
        if hasattr(self, '_consolidated_uptime_results') and self._consolidated_uptime_results:
            network_statistics = self._consolidated_uptime_results.get('network_statistics', {})
            network_flag_statistics = self._consolidated_uptime_results.get('network_flag_statistics', {})
            network_middle_statistics = self._consolidated_uptime_results.get('network_middle_statistics', {})
            network_other_statistics = self._consolidated_uptime_results.get('network_other_statistics', {})
            
            # Use 1-month network mean for overall uptime as requested
            if network_statistics.get('1_month', {}).get('mean') is not None:
                health_metrics['overall_uptime'] = network_statistics['1_month']['mean']
            elif hasattr(self, 'network_uptime_percentiles') and self.network_uptime_percentiles:
                health_metrics['overall_uptime'] = self.network_uptime_percentiles['average']
            else:
                health_metrics['overall_uptime'] = 0.0
                
            # Store uptime percentiles if available
            if hasattr(self, 'network_uptime_percentiles') and self.network_uptime_percentiles:
                health_metrics['uptime_percentiles'] = self.network_uptime_percentiles['percentiles']
            else:
                health_metrics['uptime_percentiles'] = None
            
            # Reuse all existing role-specific calculations from consolidated uptime processing
            # This follows DRY/DIY principle by using already computed statistics
            # Exit and Guard statistics come from flag-specific network statistics
            # Middle statistics come from consolidated middle relay calculations
            # Other statistics come from consolidated other relay calculations
            
            for period in ['1_month', '6_months', '1_year', '5_years']:
                # Exit relay statistics - reuse existing calculation
                if network_flag_statistics.get('Exit', {}).get(period, {}).get('mean') is not None:
                    exit_mean = network_flag_statistics['Exit'][period]['mean']
                    exit_median = network_flag_statistics['Exit'][period].get('median', exit_mean)
                else:
                    exit_mean = 0.0
                    exit_median = 0.0
            
                # Guard relay statistics - reuse existing calculation  
                if network_flag_statistics.get('Guard', {}).get(period, {}).get('mean') is not None:
                    guard_mean = network_flag_statistics['Guard'][period]['mean']
                    guard_median = network_flag_statistics['Guard'][period].get('median', guard_mean)
                else:
                    guard_mean = 0.0
                    guard_median = 0.0
                
                # Middle relay statistics - reuse existing consolidated calculation
                if network_middle_statistics.get(period, {}).get('mean') is not None:
                    middle_mean = network_middle_statistics[period]['mean']
                    middle_median = network_middle_statistics[period].get('median', middle_mean)
                else:
                    middle_mean = 0.0
                    middle_median = 0.0
                
                # Other relay statistics - reuse existing consolidated calculation
                if network_other_statistics.get(period, {}).get('mean') is not None:
                    other_mean = network_other_statistics[period]['mean']
                    other_median = network_other_statistics[period].get('median', other_mean)
                else:
                    other_mean = 0.0
                    other_median = 0.0
                
                # NEW: Additional flag-specific uptime calculations
                # Authority uptime statistics
                if network_flag_statistics.get('Authority', {}).get(period, {}).get('mean') is not None:
                    authority_mean = network_flag_statistics['Authority'][period]['mean']
                    authority_median = network_flag_statistics['Authority'][period].get('median', authority_mean)
                else:
                    authority_mean = 0.0
                    authority_median = 0.0
                
                # V2Dir uptime statistics
                if network_flag_statistics.get('V2Dir', {}).get(period, {}).get('mean') is not None:
                    v2dir_mean = network_flag_statistics['V2Dir'][period]['mean']
                    v2dir_median = network_flag_statistics['V2Dir'][period].get('median', v2dir_mean)
                else:
                    v2dir_mean = 0.0
                    v2dir_median = 0.0
                
                # HSDir uptime statistics
                if network_flag_statistics.get('HSDir', {}).get(period, {}).get('mean') is not None:
                    hsdir_mean = network_flag_statistics['HSDir'][period]['mean']
                    hsdir_median = network_flag_statistics['HSDir'][period].get('median', hsdir_mean)
                else:
                    hsdir_mean = 0.0
                    hsdir_median = 0.0
                
                # REFACTORED: Consistent naming pattern for all periods - {role}_uptime_{period}_{statistic}
                # Eliminates redundant variables and special cases for better maintainability
                role_data = [
                    ('exit', exit_mean, exit_median),
                    ('guard', guard_mean, guard_median),
                    ('middle', middle_mean, middle_median),
                    ('other', other_mean, other_median),
                    ('authority', authority_mean, authority_median),
                    ('v2dir', v2dir_mean, v2dir_median),
                    ('hsdir', hsdir_mean, hsdir_median)
                ]
                
                for role, mean_val, median_val in role_data:
                    health_metrics[f'{role}_uptime_{period}_mean'] = mean_val
                    health_metrics[f'{role}_uptime_{period}_median'] = median_val
            
        else:
            # Initialize to 0 when no consolidated uptime results available
            health_metrics['overall_uptime'] = 0.0
            health_metrics['uptime_percentiles'] = None
            
            # REFACTORED: Consistent fallback initialization using unified pattern
            uptime_periods = ['1_month', '6_months', '1_year', '5_years']
            roles = ['exit', 'guard', 'middle', 'other', 'authority', 'v2dir', 'hsdir']
            statistics = ['mean', 'median']
            
            # Generate all uptime keys using consistent pattern: {role}_uptime_{period}_{statistic}
            uptime_keys = [f'{role}_uptime_{period}_{stat}' for role in roles for period in uptime_periods for stat in statistics]
            
            for key in uptime_keys:
                health_metrics[key] = 0.0
        
        # Percentage calculations for participation metrics
        health_metrics.update({
            'relays_with_family_percentage': (relays_with_family / total_relays * 100) if total_relays > 0 else 0.0,
            'relays_without_family_percentage': (relays_without_family / total_relays * 100) if total_relays > 0 else 0.0,
            'relays_with_contact_percentage': (relays_with_contact / total_relays * 100) if total_relays > 0 else 0.0,
            'relays_without_contact_percentage': (relays_without_contact / total_relays * 100) if total_relays > 0 else 0.0
        })
        
        # Final calculations - reuse existing data
        countries_count = health_metrics['countries_count']
        as_count = health_metrics['unique_as_count']
        
        health_metrics.update({
            'avg_as_per_country': round(as_count / countries_count, 1) if countries_count > 0 else 0.0,
            'avg_aroi_per_as': round(health_metrics['aroi_operators_count'] / as_count, 1) if as_count > 0 else 0.0,
            'avg_families_per_as': round(health_metrics['families_count'] / as_count, 1) if as_count > 0 else 0.0
        })
        
        # Add CW/BW ratio metrics from intelligence engine (same as contact performance insights)
        if hasattr(self, 'json') and 'smart_context' in self.json:
            # Extract contact intelligence data which contains network-wide CW/BW ratios
            contact_intelligence = self.json['smart_context'].get('contact_intelligence', {}).get('template_optimized', {})
            
            # Find any contact's data to get the network-wide ratios (all contacts have same network values)
            network_ratios = {}
            for contact_hash, contact_data in contact_intelligence.items():
                if isinstance(contact_data, dict):
                    # Extract network-wide performance ratios
                    if 'performance_network_overall_ratio' in contact_data:
                        network_ratios['overall_ratio_mean'] = contact_data['performance_network_overall_ratio']
                    if 'performance_network_overall_median' in contact_data:
                        network_ratios['overall_ratio_median'] = contact_data['performance_network_overall_median']
                    if 'performance_network_guard_ratio' in contact_data:
                        network_ratios['guard_ratio_mean'] = contact_data['performance_network_guard_ratio']
                    if 'performance_network_guard_median' in contact_data:
                        network_ratios['guard_ratio_median'] = contact_data['performance_network_guard_median']
                    if 'performance_network_exit_ratio' in contact_data:
                        network_ratios['exit_ratio_mean'] = contact_data['performance_network_exit_ratio']
                    if 'performance_network_exit_median' in contact_data:
                        network_ratios['exit_ratio_median'] = contact_data['performance_network_exit_median']
                    break  # Only need one contact since all have same network values
            
            # Add to health metrics with defaults if not found
            health_metrics.update({
                'cw_bw_ratio_overall_mean': network_ratios.get('overall_ratio_mean', '0'),
                'cw_bw_ratio_overall_median': network_ratios.get('overall_ratio_median', '0'),
                'cw_bw_ratio_guard_mean': network_ratios.get('guard_ratio_mean', '0'),
                'cw_bw_ratio_guard_median': network_ratios.get('guard_ratio_median', '0'),
                'cw_bw_ratio_exit_mean': network_ratios.get('exit_ratio_mean', '0'),
                'cw_bw_ratio_exit_median': network_ratios.get('exit_ratio_median', '0')
            })
        else:
            # Fallback when smart_context not available
            health_metrics.update({
                'cw_bw_ratio_overall_mean': '0',
                'cw_bw_ratio_overall_median': '0',
                'cw_bw_ratio_guard_mean': '0',
                'cw_bw_ratio_guard_median': '0',
                'cw_bw_ratio_exit_mean': '0',
                'cw_bw_ratio_exit_median': '0'
        })
        
        # === AROI VALIDATION METRICS ===
        # Calculate AROI validation metrics for operator participation
        # Data was fetched in parallel by coordinator API worker
        try:
            from .aroi_validation import calculate_aroi_validation_metrics
            
            # Get pre-fetched validation data (attached by coordinator)
            validation_data = getattr(self, 'aroi_validation_data', None)
            
            # Calculate validation metrics (relay AND operator level in single pass)
            validation_metrics = calculate_aroi_validation_metrics(
                self.json.get('relays', []), 
                validation_data,
                calculate_operator_metrics=True  # Enable operator-level metrics in same pass
            )
            
            # Store validation_map for reuse by contact pages (avoids rebuilding 3,000+ times)
            self.validation_map = validation_metrics.pop('_validation_map', {})
            
            # Add validation metrics to health_metrics
            health_metrics.update(validation_metrics)
            
            # Calculate total relays with AROI (validated + invalid)
            total_relays_with_aroi = (
                validation_metrics.get('aroi_validated_count', 0) + 
                validation_metrics.get('aroi_unvalidated_count', 0)
            )
            
            # Calculate percentages relative to AROI relays
            if total_relays_with_aroi > 0:
                aroi_validated_pct_of_aroi = (
                    validation_metrics['aroi_validated_count'] / total_relays_with_aroi * 100
                )
                aroi_invalid_pct_of_aroi = (
                    validation_metrics['aroi_unvalidated_count'] / total_relays_with_aroi * 100
                )
            else:
                aroi_validated_pct_of_aroi = 0.0
                aroi_invalid_pct_of_aroi = 0.0
            
            # Add derived metrics
            health_metrics['total_relays_with_aroi'] = total_relays_with_aroi
            health_metrics['total_relays_with_aroi_percentage'] = (
                (total_relays_with_aroi / total_relays_count * 100) 
                if total_relays_count > 0 else 0.0
            )
            health_metrics['aroi_validated_percentage_of_aroi'] = aroi_validated_pct_of_aroi
            health_metrics['aroi_invalid_percentage_of_aroi'] = aroi_invalid_pct_of_aroi
            
            # Calculate relays without AROI (total - validated - unvalidated)
            relays_without_aroi = total_relays_count - total_relays_with_aroi
            health_metrics['relays_without_aroi'] = relays_without_aroi
            health_metrics['relays_without_aroi_percentage'] = (
                (relays_without_aroi / total_relays_count * 100)
                if total_relays_count > 0 else 0.0
            )
            
            # Operator-level metrics calculated in aroi_validation.py (same pass as relay metrics)
            # Extract validated domain set for IPv6 calculation
            validated_domain_set = validation_metrics.get('_validated_domain_set', set())
            validated_aroi_domains = validation_metrics.get('validated_aroi_domains_count', 0)
            unique_aroi_domains_count = validation_metrics.get('unique_aroi_domains_count', 0)
            
            # Store validated domain set for vanity URL generation later
            self.validated_aroi_domains = validated_domain_set
            
            # UPDATE aroi_operators_count to use accurate AROI domain count (Option B: Global Replace)
            health_metrics['aroi_operators_count'] = unique_aroi_domains_count
            
            # Get IPv6 status dict from earlier calculation
            operator_ipv6_status = health_metrics.pop('_temp_operator_ipv6_status', {})
            
            # Count IPv6 support ONLY among validated operators (mutually exclusive)
            both_ipv4_ipv6_aroi_operators = sum(1 for domain in validated_domain_set 
                                            if domain in operator_ipv6_status and operator_ipv6_status[domain]['has_dual_stack'])
            ipv4_only_aroi_operators = sum(1 for domain in validated_domain_set
                                       if domain in operator_ipv6_status and not operator_ipv6_status[domain]['has_dual_stack'] and operator_ipv6_status[domain]['has_ipv4_only'])
            
            health_metrics['ipv4_only_aroi_operators'] = ipv4_only_aroi_operators
            health_metrics['both_ipv4_ipv6_aroi_operators'] = both_ipv4_ipv6_aroi_operators
            
            # Calculate IPv6 operator percentages based on validated operators count (124)
            if validated_aroi_domains > 0:
                health_metrics['ipv4_only_aroi_operators_percentage'] = (ipv4_only_aroi_operators / validated_aroi_domains * 100)
                health_metrics['both_ipv4_ipv6_aroi_operators_percentage'] = (both_ipv4_ipv6_aroi_operators / validated_aroi_domains * 100)
            else:
                health_metrics['ipv4_only_aroi_operators_percentage'] = 0.0
                health_metrics['both_ipv4_ipv6_aroi_operators_percentage'] = 0.0
            
            # Calculate average relays per operator (now using accurate count)
            aroi_operators_count = health_metrics.get('aroi_operators_count', 0)
            if aroi_operators_count > 0:
                health_metrics['avg_relays_per_aroi_operator'] = round(
                    total_relays_with_aroi / aroi_operators_count, 2
                )
            else:
                health_metrics['avg_relays_per_aroi_operator'] = 0.0
            
            # AROI validation progress messages are now handled by coordinator API worker
            # No need for separate progress output here since it's fetched in parallel
                    
        except Exception as e:
            # Graceful fallback if validation data unavailable
            if self.progress:
                print(f"⚠️  AROI Validation: Error loading data: {e}")
            health_metrics.update({
                'aroi_validated_count': 0,
                'aroi_unvalidated_count': 0,
                'aroi_no_proof_count': 0,
                'relays_no_aroi': 0,
                'relays_without_aroi': total_relays_count,  # All relays have no AROI if validation fails
                'relays_without_aroi_percentage': 100.0 if total_relays_count > 0 else 0.0,
                'aroi_validated_percentage': 0.0,
                'aroi_unvalidated_percentage': 0.0,
                'aroi_no_proof_percentage': 0.0,
                'relays_no_aroi_percentage': 0.0,
                'aroi_validation_success_rate': 0.0,
                'dns_rsa_success_rate': 0.0,
                'uri_rsa_success_rate': 0.0,
                'validation_data_available': False,
                'total_relays_with_aroi': 0,
                'total_relays_with_aroi_percentage': 0.0,
                'aroi_validated_percentage_of_aroi': 0.0,
                'aroi_invalid_percentage_of_aroi': 0.0,
                'avg_relays_per_aroi_operator': 0.0,
                'unique_aroi_domains_count': 0,
                'validated_aroi_domains_count': 0,
                'invalid_aroi_domains_count': 0,
                'validated_aroi_domains_percentage': 0.0,
                'invalid_aroi_domains_percentage': 0.0,
                'relay_error_top5': [],
                'operator_error_top5': [],
                'dns_error_top5': [],
                'uri_error_top5': [],
                'no_aroi_reasons_top5': [],
                'top_operators_text': 'No data available',
                'ipv4_only_aroi_operators': 0,
                'both_ipv4_ipv6_aroi_operators': 0,
                'ipv4_only_aroi_operators_percentage': 0.0,
                'both_ipv4_ipv6_aroi_operators_percentage': 0.0
            })
        
        # OPTIMIZATION: Pre-format all template strings to eliminate Jinja2 formatting overhead
        # Template formatting in Jinja2 is 3-5x slower than Python formatting
        self._preformat_network_health_template_strings(health_metrics)
        
        # Store the complete health metrics
        self.json['network_health'] = health_metrics
