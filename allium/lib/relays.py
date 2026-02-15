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
            relay["_uptime_datapoints"] = {}
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
        from .country_utils import calculate_as_rarity_score as _as_rarity_score, assign_as_rarity_tier as _as_rarity_tier, compute_as_cw_thresholds
        # Compute dynamic CW thresholds once from the AS data
        _cw_thresholds = compute_as_cw_thresholds(self.json.get('sorted', {}).get('as', {}))
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
                        
                        # Pre-compute AS rarity scores using dynamic thresholds
                        if category == "as":
                            cw = data.get("consensus_weight_fraction", 0)
                            contacts = data.get("unique_contact_count", 0)
                            data["as_rarity_score"] = _as_rarity_score(cw, contacts, _cw_thresholds)
                            data["as_rarity_tier"] = _as_rarity_tier(data["as_rarity_score"])
                        
                        # Cleanup sets to save memory
                        data.pop("unique_contact_set", None)
                        data.pop("unique_aroi_set", None)

    def _propagate_as_rarity(self):
        """Propagate pre-computed AS rarity data from sorted['as'] to each relay dict."""
        as_data = self.json.get('sorted', {}).get('as', {})
        _empty = {}
        for relay in self.json['relays']:
            e = as_data.get(relay.get('as', ''), _empty)
            relay['as_rarity_score'] = e.get('as_rarity_score', 0)
            relay['as_rarity_tier'] = e.get('as_rarity_tier', 'common')
            relay['as_operator_count'] = e.get('unique_contact_count', 0)
            cw = e.get('consensus_weight_fraction', 0)
            relay['as_cw_label'] = f"{cw * 100:.2f}%" if cw >= 0.0005 else ("<0.05%" if cw > 0 else "0%")

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
                
                # Extract smart display name for contact column
                # Priority: AROI domain > full email > person name > raw contact
                aroi_domain = data.get("aroi_domain")
                contact_str = data.get("contact", "")
                display_name = extract_contact_display_name(contact_str, aroi_domain)
                
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
                    "display_name": display_name,  # Smart display name for contact column
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
        """Pre-format all template strings to eliminate Jinja2 formatting overhead."""
        from .network_health import preformat_network_health_template_strings
        preformat_network_health_template_strings(health_metrics)

    def _calculate_network_health_metrics(self):
        """Calculate network health metrics. Delegates to network_health module."""
        from .network_health import calculate_network_health_metrics
        calculate_network_health_metrics(self)
