"""
File: relays.py

Relays class object consisting of relays (list of dict) and onionoo fetch
timestamp
"""

import functools
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
from .string_utils import format_percentage_from_fraction, extract_contact_display_name
from .bandwidth_formatter import (
    BandwidthFormatter, 
    determine_unit, 
    get_divisor_for_unit, 
    format_bandwidth_with_unit,
    determine_unit_filter, 
    format_bandwidth_filter
)
from .stability_utils import compute_relay_stability
from .intelligence_engine import IntelligenceEngine
from .ip_utils import is_private_ip_address, determine_ipv6_support
from .time_utils import (
    parse_onionoo_timestamp,
    create_time_thresholds,
    format_timestamp_gmt,
    format_time_ago,
)
import logging
import statistics
from datetime import datetime, timedelta

ABS_PATH = os.path.dirname(os.path.abspath(__file__))

# Bandwidth formatting utilities now imported from bandwidth_formatter.py


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


class Relays:
    """Relay class consisting of processing routines and onionoo data"""

    def __init__(self, output_dir, onionoo_url, relay_data, use_bits=False, progress=False, start_time=None, progress_step=0, total_steps=53, filter_downtime_days=7, base_url='', progress_logger=None, mp_workers=4):
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
        self._propagate_as_rarity()  # Copy AS rarity scores to each relay for templates
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
                    # Store datapoints for AROI leaderboard breakdown display
                    relay["_uptime_datapoints"] = relay_uptime_data[fingerprint].get('uptime_datapoints', {})
                    # Store flag data for flag reliability analysis
                    relay["_flag_uptime_data"] = relay_uptime_data[fingerprint]['flag_data']
                else:
                    relay["uptime_percentages"] = {'1_month': 0.0, '6_months': 0.0, '1_year': 0.0, '5_years': 0.0}
                    relay["_uptime_datapoints"] = {}
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
            # PERF: Compute timestamp once for all relays (avoids ~10k time.time() calls)
            now_timestamp = time.time()
            
            for relay in self.json["relays"]:
                fingerprint = relay.get('fingerprint', '')
                
                # Apply bandwidth data from consolidated processing
                if fingerprint in relay_bandwidth_data:
                    bw_data = relay_bandwidth_data[fingerprint]
                    relay["bandwidth_averages"] = bw_data['bandwidth_averages']
                    # Store flag bandwidth data for flag bandwidth analysis
                    relay["_flag_bandwidth_data"] = bw_data['flag_data']
                    # Merge overload fields from bandwidth endpoint
                    if bw_data.get('overload_ratelimits'):
                        relay['overload_ratelimits'] = bw_data['overload_ratelimits']
                    if bw_data.get('overload_fd_exhausted'):
                        relay['overload_fd_exhausted'] = bw_data['overload_fd_exhausted']
                else:
                    relay["bandwidth_averages"] = {'6_months': 0.0, '1_year': 0.0, '5_years': 0.0}
                    relay["_flag_bandwidth_data"] = {}
                
                # Compute stability using helper with bandwidth formatter
                # (overload_general_timestamp from /details is already in relay,
                #  overload_ratelimits/overload_fd_exhausted now merged from /bandwidth)
                relay.update(compute_relay_stability(relay, now_timestamp, self.bandwidth_formatter))
            
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
            import time as _time
            from .consensus import CollectorFetcher, format_relay_consensus_evaluation
            from .consensus.collector_fetcher import calculate_consensus_requirement, discover_authorities
            from .relay_diagnostics import generate_relay_issues
            
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
            # PERF: Compute timestamp once for all relays (avoid ~10k time.time() calls)
            now_timestamp = _time.time()
            
            for relay in self.json["relays"]:
                fingerprint = relay.get('fingerprint', '').upper()
                if not fingerprint:
                    continue
                
                # Get raw consensus evaluation from fetcher
                raw_consensus_evaluation = fetcher.get_relay_consensus_evaluation(fingerprint, authority_count)
                
                # Calculate relay uptime from last_restarted (Onionoo data)
                # This is the relay's self-reported uptime from its descriptor
                relay_uptime = None
                last_restarted = relay.get('last_restarted')
                if last_restarted:
                    try:
                        from datetime import datetime, timezone
                        # Handle ISO format with optional timezone
                        if last_restarted.endswith('Z'):
                            restart_time = datetime.fromisoformat(last_restarted.replace('Z', '+00:00'))
                        elif '+' in last_restarted or last_restarted.count('-') > 2:
                            restart_time = datetime.fromisoformat(last_restarted)
                        else:
                            # Assume UTC if no timezone
                            restart_time = datetime.fromisoformat(last_restarted).replace(tzinfo=timezone.utc)
                        relay_uptime = (datetime.now(timezone.utc) - restart_time).total_seconds()
                    except (ValueError, TypeError):
                        pass
                
                # Format for template display, passing current flags, observed_bandwidth, and relay_uptime
                # Note: observed_bandwidth (from descriptor) is the actual bandwidth for Guard eligibility
                # NOT the scaled consensus weight or vote Measured value
                current_flags = relay.get('flags', [])
                observed_bandwidth = relay.get('observed_bandwidth', 0)
                version = relay.get('version')
                recommended_version = relay.get('recommended_version')
                formatted_consensus_evaluation = format_relay_consensus_evaluation(
                    raw_consensus_evaluation, flag_thresholds, current_flags, observed_bandwidth,
                    use_bits=self.use_bits,  # Pass use_bits for consistent bandwidth formatting
                    relay_uptime=relay_uptime,  # Pass relay uptime from Onionoo for Stable comparison
                    version=version,  # Pass version for outdated version detection
                    recommended_version=recommended_version  # Pass recommended status
                )
                
                # Attach to relay
                relay['consensus_evaluation'] = formatted_consensus_evaluation
                
                # Generate full diagnostics including overload issues
                # (overload data was merged in _reprocess_bandwidth_data)
                relay['diagnostics'] = {
                    'issues': generate_relay_issues(
                        relay,
                        consensus_data=raw_consensus_evaluation,
                        use_bits=self.use_bits,
                        now_timestamp=now_timestamp  # PERF: Reuse timestamp
                    )
                }
                
                if formatted_consensus_evaluation.get('available'):
                    evaluation_count += 1
            
            self._log_progress(f"Processed consensus evaluation for {evaluation_count} relays")
            
        except Exception as e:
            # Fallback gracefully if collector processing fails
            print(f"Warning: Collector data processing failed ({e}), continuing without consensus evaluation")
            import traceback
            traceback.print_exc()

    def _calculate_network_bandwidth_percentiles(self, bandwidth_data):
        """Calculate network-wide bandwidth percentiles."""
        from .flag_analysis import calculate_network_bandwidth_percentiles
        return calculate_network_bandwidth_percentiles(bandwidth_data, self)

    def _apply_statistical_coloring(self, network_statistics):
        """Apply statistical coloring to relay uptime percentages."""
        from .flag_analysis import apply_statistical_coloring
        apply_statistical_coloring(self.json["relays"], network_statistics)

    def _process_flag_bandwidth_display(self, network_flag_statistics):
        """Process flag bandwidth data into display format."""
        from .flag_analysis import process_flag_bandwidth_display
        process_flag_bandwidth_display(self.json["relays"], network_flag_statistics, self.bandwidth_formatter)

    def _process_flag_uptime_display(self, network_flag_statistics):
        """Process flag uptime data into display format."""
        from .flag_analysis import process_flag_uptime_display
        process_flag_uptime_display(self.json["relays"], network_flag_statistics)

    def _basic_uptime_processing(self):
        """Fallback basic uptime processing."""
        from .flag_analysis import basic_uptime_processing
        basic_uptime_processing(self.json["relays"])

    def _sort_by_observed_bandwidth(self):
        """Sort relays by observed bandwidth."""
        from .flag_analysis import sort_by_observed_bandwidth
        sort_by_observed_bandwidth(self.json)

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
        """Calculate network totals using three counting methodologies."""
        from .categorization import calculate_network_totals
        return calculate_network_totals(self)

    def _sort(self, relay, idx, k, v, cw, cw_fraction):
        """Populate self.sorted dictionary with values from relay."""
        from .categorization import sort_relay
        sort_relay(self, relay, idx, k, v, cw, cw_fraction)

    def _categorize(self):
        """Iterate over relays and sort into categories."""
        from .categorization import categorize
        categorize(self)

    def _calculate_consensus_weight_fractions(self, total_guard_cw, total_middle_cw, total_exit_cw):
        """Calculate consensus weight fractions for guard, middle, and exit relays."""
        from .categorization import calculate_consensus_weight_fractions
        calculate_consensus_weight_fractions(self, total_guard_cw, total_middle_cw, total_exit_cw)

    def _calculate_and_cache_family_statistics(self, total_guard_cw, total_middle_cw, total_exit_cw):
        """Calculate family network totals and centralization risk statistics."""
        from .categorization import calculate_and_cache_family_statistics
        calculate_and_cache_family_statistics(self, total_guard_cw, total_middle_cw, total_exit_cw)

    def _finalize_unique_as_counts(self):
        """Convert unique AS sets to counts and clean up memory."""
        from .categorization import finalize_unique_as_counts
        finalize_unique_as_counts(self)

    def _propagate_as_rarity(self):
        """Propagate AS rarity data from sorted AS data to each relay."""
        from .categorization import propagate_as_rarity
        propagate_as_rarity(self)

    def _calculate_contact_derived_data(self):
        """Calculate derived contact data: primary countries and bandwidth means."""
        from .categorization import calculate_contact_derived_data
        calculate_contact_derived_data(self)

    def _precompute_display_values(self):
        """Pre-compute display strings for misc listing pages."""
        from .categorization import precompute_display_values
        precompute_display_values(self)

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
        
        # Use cached AROI validation timestamp (same for all contacts)
        aroi_validation_timestamp = self._aroi_validation_timestamp
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

    def _precompute_all_family_page_data(self):
        """
        PERF OPTIMIZATION: Pre-compute all family page data using parallel processing.
        
        Family pages were 6-10x slower than contact pages because they computed
        expensive validation status on every page render. By pre-computing this data
        during the Data Processing phase, we achieve similar speedup to contact pages.
        
        Pre-computes for each family:
        - contact_validation_status: AROI validation status for the family's relays
        - network_position: Pre-computed network position data
        """
        if "family" not in self.json["sorted"]:
            return
        
        family_hashes = list(self.json["sorted"]["family"].keys())
        if not family_hashes:
            return
        
        # Use multiprocessing if available and beneficial
        use_mp = (self.mp_workers > 0 and len(family_hashes) >= 100 and 
                  hasattr(mp, 'get_context'))
        
        if use_mp:
            try:
                self._precompute_families_parallel(family_hashes)
                return
            except Exception as e:
                # Fall back to sequential if parallel fails
                if self.progress:
                    self._log_progress(f"Parallel family precomputation failed ({e}), using sequential...")
        
        # Sequential fallback
        for family_hash in family_hashes:
            self._precompute_single_family(family_hash)
    
    def _precompute_single_family(self, family_hash):
        """Precompute data for a single family (used by both sequential and parallel paths).
        
        Stores precomputed values directly on family_data for simple access.
        """
        family_data = self.json["sorted"]["family"][family_hash]
        
        # Get member relays for this family
        members = [self.json["relays"][idx] for idx in family_data.get("relays", [])]
        if not members:
            return
        
        # Pre-compute AROI validation status (use cached if available)
        family_data["contact_validation_status"] = (family_data.get("aroi_validation_full") or 
                                                     self._get_contact_validation_status(members))
        
        # Pre-compute network position using DRY helper
        family_data["network_position"] = _compute_network_position_safe(
            family_data["guard_count"], family_data["middle_count"], 
            family_data["exit_count"], len(members))
    
    def _precompute_families_parallel(self, family_hashes):
        """Parallel family precomputation using fork() with imap_unordered.
        
        Mirrors _precompute_contacts_parallel for consistency.
        """
        # Use fork context for efficient memory sharing
        ctx = mp.get_context('fork')
        
        # Prepare arguments for worker function (single-element tuple)
        worker_args = [(family_hash,) for family_hash in family_hashes]
        
        total_families = len(family_hashes)
        processed = 0
        chunk_size = max(50, total_families // (self.mp_workers * 4))
        
        # Initialize workers with self reference (fork shares memory)
        with ctx.Pool(self.mp_workers, _init_precompute_worker, (self,)) as pool:
            # Use imap_unordered for streaming results
            for family_hash, precomputed_data in pool.imap_unordered(
                _precompute_family_worker, worker_args, chunksize=chunk_size
            ):
                # Apply result directly to family data
                if precomputed_data and family_hash in self.json["sorted"]["family"]:
                    family_data = self.json["sorted"]["family"][family_hash]
                    for key, value in precomputed_data.items():
                        family_data[key] = value
                
                # Progress reporting
                processed += 1
                if processed % 1000 == 0:
                    self._log_progress(f"Pre-computed {processed}/{total_families} families...")

    def _generate_aroi_leaderboards(self):
        """
        Generate AROI operator leaderboards using pre-processed relay data.
        
        PERFORMANCE: This method was optimized to pre-build uptime/bandwidth maps once
        instead of rebuilding them for each of ~3,000 contacts × 4 metric calculations.
        This reduced map-building iterations from ~132M to ~21K (99.98% reduction).
        """
        self._log_progress("Generating AROI operator leaderboards...")
        self.json['aroi_leaderboards'] = _calculate_aroi_leaderboards(self)
        contact_count = len(self.json.get('sorted', {}).get('contact', {}))
        self._log_progress(f"AROI leaderboards generated for {contact_count} operators")

    def _generate_smart_context(self):
        """
        Generate smart context information using intelligence engine
        """
        # IntelligenceEngine imported at module level for performance
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
        os.makedirs(output_path)

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

            os.makedirs(dir_path, exist_ok=True)
            # relay_subset passed directly to template for thread safety (no shared state)
            
            bandwidth_unit = self.bandwidth_formatter.determine_unit(i["bandwidth"])
            # Format all bandwidth values using the same unit
            bandwidth = self.bandwidth_formatter.format_bandwidth_with_unit(i["bandwidth"], bandwidth_unit)
            guard_bandwidth = self.bandwidth_formatter.format_bandwidth_with_unit(i["guard_bandwidth"], bandwidth_unit)
            middle_bandwidth = self.bandwidth_formatter.format_bandwidth_with_unit(i["middle_bandwidth"], bandwidth_unit)
            exit_bandwidth = self.bandwidth_formatter.format_bandwidth_with_unit(i["exit_bandwidth"], bandwidth_unit)
            
            # Calculate network position using DRY helper
            network_position = _compute_network_position_safe(
                i["guard_count"], i["middle_count"], i["exit_count"], len(members))
            network_position_display = network_position.get('formatted_string', 'unknown')
            
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
                                             self._get_contact_validation_status(members))
                aroi_validation_timestamp = self._aroi_validation_timestamp
            
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
                contact_validation_status = self._get_contact_validation_status(members)
            aroi_validation_timestamp = self._aroi_validation_timestamp
        
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
            'base_url': self.base_url,
        }

    def _write_pages_parallel(self, k, sorted_values, template, output_path, the_prefixed, start_time):
        """Parallel page generation using fork() for significant speedup on large page sets.
        
        OPTIMIZED: Now passes only (html_path, value) to workers instead of full template args.
        Workers build template args from forked memory, avoiding ~300KB/page IPC serialization.
        This dramatically improves performance for large page sets like families (105+ members avg).
        """
        validated_aroi_domains = getattr(self, 'validated_aroi_domains', set())
        page_args = []
        vanity_url_tasks = []  # Collect vanity URL tasks for post-processing
        
        for v in sorted_values:
            v = v.replace("..", "").replace("/", "_")
            i = self.json["sorted"][k][v]
            dir_path = os.path.join(output_path, v.lower() if k == "flag" else v)
            os.makedirs(dir_path, exist_ok=True)
            html_path = os.path.join(dir_path, "index.html")
            # OPTIMIZED: Pass only (html_path, value) - workers build template args from forked memory
            page_args.append((html_path, v))
            
            # Collect vanity URL tasks for contact pages (to be processed after parallel generation)
            # Uses precomputed aroi_domain to avoid re-fetching members
            if k == "contact" and self.base_url and i.get("is_validated_aroi"):
                aroi_domain = i.get("aroi_domain")
                if aroi_domain and aroi_domain != "none":
                    vanity_url_tasks.append((html_path, aroi_domain, output_path))
        
        pool = None
        try:
            ctx = mp.get_context('fork')
            # Initialize workers with page_type and shared data for building template args
            pool = ctx.Pool(self.mp_workers, _init_mp_worker, 
                           (self, template, k, the_prefixed, validated_aroi_domains))
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
            self.progress_logger.log(f"{k} page generation complete - Generated {len(page_args)} pages in {total_time:.2f}s")
            if self.progress:
                print(f"    🚀 Parallel: {self.mp_workers} workers, {total_time/len(page_args)*1000:.1f}ms/page avg")
        except Exception as e:
            # Ensure pool is properly terminated before fallback
            if pool is not None:
                try:
                    pool.terminate()
                    pool.join()
                except Exception:
                    pass  # Ignore cleanup errors
            
            self._log_progress(f"Multiprocessing failed ({e}), falling back to sequential...")
            self.mp_workers = 0
            
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

        # Optimization: Move imports and setup outside the loop (10k+ iterations)
        from .page_context import StandardTemplateContexts
        standard_contexts = StandardTemplateContexts(self)
        
        # Optimization: Pre-fetch collections for fast lookup
        # Safely get contact map - avoiding 3-level .get() in loop
        contact_map = self.json.get("sorted", {}).get("contact", {})
        
        # Optimization: Cache validated domains set
        validated_aroi_domains = getattr(self, 'validated_aroi_domains', set())

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
                relay=relay, page_ctx=page_ctx, relays=self, contact_display_data=contact_display_data,
                contact_validation_status=contact_validation_status,
                validated_aroi_domains=validated_aroi_domains,
                base_url=self.base_url
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
    
    @functools.cached_property
    def _aroi_validation_timestamp(self):
        """
        Cached AROI validation timestamp (computed once, reused for all pages).
        
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
        """Generate AROI leaderboard rankings for a specific contact."""
        from .operator_analysis import generate_contact_rankings
        return generate_contact_rankings(contact_hash, self)

    def _get_leaderboard_category_info(self, category):
        """Get display information for a leaderboard category."""
        from .operator_analysis import get_leaderboard_category_info
        return get_leaderboard_category_info(category)

    def _calculate_operator_reliability(self, contact_hash, operator_relays):
        """Calculate comprehensive reliability statistics for an operator."""
        from .operator_analysis import calculate_operator_reliability
        return calculate_operator_reliability(contact_hash, operator_relays, self)

    def _format_intelligence_rating(self, rating_text):
        """Format intelligence rating text with color coding."""
        from .operator_analysis import format_intelligence_rating
        return format_intelligence_rating(rating_text)

    def _compute_contact_display_data(self, i, bandwidth_unit, operator_reliability, v, members):
        """Compute contact-specific display data for contact pages."""
        from .operator_analysis import compute_contact_display_data
        return compute_contact_display_data(i, bandwidth_unit, operator_reliability, v, members, self)

    def _compute_contact_flag_analysis(self, contact_hash, members):
        """Compute flag analysis for contact operator."""
        from .operator_analysis import compute_contact_flag_analysis
        return compute_contact_flag_analysis(contact_hash, members, self)

    def _compute_contact_flag_bandwidth_analysis(self, contact_hash, members):
        """Compute flag bandwidth analysis for contact operator."""
        from .operator_analysis import compute_contact_flag_bandwidth_analysis
        return compute_contact_flag_bandwidth_analysis(contact_hash, members, self)

    def _process_operator_flag_bandwidth_reliability(self, operator_flag_data, network_flag_statistics):
        """Process operator flag bandwidth data into display format."""
        from .operator_analysis import process_operator_flag_bandwidth_reliability
        return process_operator_flag_bandwidth_reliability(operator_flag_data, network_flag_statistics, self)

    def _process_operator_flag_reliability(self, operator_flag_data, network_flag_statistics):
        """Process flag reliability metrics for an operator."""
        from .operator_analysis import process_operator_flag_reliability
        return process_operator_flag_reliability(operator_flag_data, network_flag_statistics)

    def _calculate_operator_downtime_alerts(self, contact_hash, operator_relays, contact_data, bandwidth_unit):
        """Calculate real-time downtime alerts for operator contact pages."""
        from .operator_analysis import calculate_operator_downtime_alerts
        return calculate_operator_downtime_alerts(contact_hash, operator_relays, contact_data, bandwidth_unit, self)

    def _calculate_uptime_display(self, relay):
        """Calculate uptime/downtime display for a single relay."""
        from .operator_analysis import calculate_uptime_display
        return calculate_uptime_display(relay, self._format_time_ago)

    def _preformat_network_health_template_strings(self, health_metrics):
        """Pre-format all template strings to eliminate Jinja2 formatting overhead."""
        from .network_health import preformat_network_health_template_strings
        preformat_network_health_template_strings(health_metrics)

    def _calculate_network_health_metrics(self):
        """Calculate network health metrics. Delegates to network_health module."""
        from .network_health import calculate_network_health_metrics
        calculate_network_health_metrics(self)
