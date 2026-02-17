"""
File: relays.py

Relays class object consisting of relays (list of dict) and onionoo fetch
timestamp
"""

import functools
import hashlib
import multiprocessing as mp
import os
import re
import time
from .aroileaders import _calculate_aroi_leaderboards
from .ip_utils import safe_parse_ip_address as _safe_parse_ip_address
from .progress_logger import ProgressLogger
from .bandwidth_formatter import (
    BandwidthFormatter,
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
from datetime import datetime, timedelta

ABS_PATH = os.path.dirname(os.path.abspath(__file__))

# Pre-compiled AROI parsing regexes (called ~7000 times per relay set)
_AROI_URL_RE = re.compile(r'\burl:(?:https?://)?([^,\s]+)', re.IGNORECASE)
_AROI_CIISS_RE = re.compile(r'\bciissversion:2\b', re.IGNORECASE)
_AROI_PROOF_RE = re.compile(r'\bproof:(dns-rsa|uri-rsa)\b', re.IGNORECASE)

# Page writing infrastructure imported from page_writer.py
from .page_writer import (
    _compute_network_position_safe,
    _compute_contact_predata,
    _compute_family_predata,
    _init_precompute_worker,
    _precompute_contact_worker,
    _precompute_family_worker,
)

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

    def enrich_with_api_data(self, uptime_data=None, bandwidth_data=None,
                             aroi_validation_data=None, collector_consensus_data=None,
                             consensus_health_data=None):
        """
        Enrich relay data with secondary API sources.
        Called by coordinator after threaded API fetch completes.

        This is the second half of the processing pipeline (after __init__).
        The full pipeline is:

        __init__:                             enrich_with_api_data:
          1. filter_and_fix_relays              7. Attach raw API data
          2. sort_by_observed_bandwidth         8. Uptime processing
          3. trim_platform                      9. Re-generate leaderboards (uses uptime)
          4. add_hashed_contact                10. Re-calculate health metrics (uses uptime)
          5. preprocess_template_data          11. Bandwidth processing
          6. categorize                        12. Re-calculate health metrics (uses bandwidth)
             propagate_as_rarity               13. Collector consensus evaluation
             generate_aroi_leaderboards        14. Pre-compute contact page data
             generate_smart_context            15. Pre-compute family page data
             calculate_network_health_metrics

        Processing order matters:
        - Uptime BEFORE leaderboards (leaderboards reuse per-relay uptime_percentages)
        - Bandwidth BEFORE health (health uses overload data from bandwidth)
        - ALL data processing BEFORE precompute (contact/family pages depend on everything)
        """
        # Step 7: Attach raw API data as attributes
        self.uptime_data = uptime_data
        self.bandwidth_data = bandwidth_data
        self.aroi_validation_data = aroi_validation_data
        self.collector_consensus_data = collector_consensus_data
        self.consensus_health_data = consensus_health_data
        # Legacy attribute for backward compatibility
        self.collector_data = None

        # Steps 8-10: Uptime processing → regenerate leaderboards + health
        if uptime_data:
            self._reprocess_uptime_data()
            self._generate_aroi_leaderboards()
            self._calculate_network_health_metrics()

        # Steps 11-12: Bandwidth processing → regenerate health
        if bandwidth_data and self.json.get('relays'):
            try:
                self._reprocess_bandwidth_data()
                self._calculate_network_health_metrics()
            except Exception as e:
                print(f"Warning: Bandwidth processing failed ({e}), continuing without bandwidth metrics")

        # Step 13: Collector consensus evaluation
        if collector_consensus_data and self.json.get('relays'):
            try:
                self._reprocess_collector_data()
            except Exception as e:
                print(f"Warning: Collector consensus processing failed ({e}), continuing without consensus evaluation")

        # Steps 14-15: Pre-compute page data (depends on ALL above)
        self._precompute_all_contact_page_data()
        self._precompute_all_family_page_data()

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
        # Uses pre-compiled regexes for performance (called ~7000 times)
        url_match = _AROI_URL_RE.search(contact)
        ciiss_match = _AROI_CIISS_RE.search(contact)
        proof_match = _AROI_PROOF_RE.search(contact)
        
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
        
        NOTE: This is now a no-op because _add_hashed_contact() already stores
        relay["aroi_domain"] during its loop (avoiding double regex parsing).
        Kept for backward compatibility in case external code calls it.
        """
        pass

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
            
            # Store AROI domain on relay now to avoid re-parsing in _process_aroi_contacts
            relay["aroi_domain"] = aroi_domain
            
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
        
        # Pre-compute consensus weight percentiles for all relays
        # Sorted ascending so we can use bisect for O(log n) lookups
        import bisect
        all_cw = sorted(relay.get('consensus_weight', 0) for relay in self.json["relays"] if relay.get('consensus_weight'))
        self._cw_sorted = all_cw
        self._cw_count = len(all_cw)
        
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
            
            # Compute consensus weight percentile rank (what % of relays have lower CW)
            cw = relay.get('consensus_weight', 0)
            if cw and self._cw_count > 0:
                rank = bisect.bisect_left(self._cw_sorted, cw)
                relay['cw_percentile'] = round(rank / self._cw_count * 100, 1)
            else:
                relay['cw_percentile'] = None
                
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
                exit_policy_summary = relay.get('exit_policy_summary', {})
                dir_address = relay.get('dir_address', '')
                formatted_consensus_evaluation = format_relay_consensus_evaluation(
                    raw_consensus_evaluation, flag_thresholds, current_flags, observed_bandwidth,
                    use_bits=self.use_bits,  # Pass use_bits for consistent bandwidth formatting
                    relay_uptime=relay_uptime,  # Pass relay uptime from Onionoo for Stable comparison
                    version=version,  # Pass version for outdated version detection
                    recommended_version=recommended_version,  # Pass recommended status
                    exit_policy_summary=exit_policy_summary,  # Pass exit policy for Exit flag analysis
                    dir_address=dir_address,  # Pass dir address for V2Dir flag analysis
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
        """Precompute data for a single contact (sequential path).
        
        Uses shared _compute_contact_predata() for DRY with the parallel worker.
        """
        precomputed = _compute_contact_predata(self, contact_hash, aroi_validation_timestamp, validated_aroi_domains)
        if precomputed:
            contact_data = self.json["sorted"]["contact"][contact_hash]
            for key, value in precomputed.items():
                contact_data[key] = value
    
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
        """Precompute data for a single family (sequential path).
        
        Uses shared _compute_family_predata() for DRY with the parallel worker.
        """
        precomputed = _compute_family_predata(self, family_hash)
        if precomputed:
            family_data = self.json["sorted"]["family"][family_hash]
            for key, value in precomputed.items():
                family_data[key] = value
    
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
        """Ensure self.output_dir exists (required for write functions)."""
        from .page_writer import create_output_dir
        create_output_dir(self)

    def write_misc(self, template, path, page_ctx=None, sorted_by=None, reverse=True, is_index=False):
        """Render and write unsorted HTML listings to disk."""
        from .page_writer import write_misc
        write_misc(self, template, path, page_ctx=page_ctx, sorted_by=sorted_by, reverse=reverse, is_index=is_index)

    def _get_directory_authorities_data(self):
        """Prepare directory authorities data for template rendering."""
        from .page_writer import get_directory_authorities_data
        return get_directory_authorities_data(self)

    def _format_time_ago(self, timestamp_str):
        """Format timestamp as multi-unit time ago (e.g., '2y 3m 2w ago')."""
        return format_time_ago(timestamp_str)

    def get_detail_page_context(self, category, value):
        """Generate page context with correct breadcrumb data for detail pages."""
        from .page_context import get_detail_page_context
        return get_detail_page_context(category, value)

    def write_pages_by_key(self, k):
        """Render and write sorted HTML relay listings to disk."""
        from .page_writer import write_pages_by_key
        write_pages_by_key(self, k)

    def _build_template_args(self, k, v, i, the_prefixed, validated_aroi_domains):
        """Build template arguments for all page types."""
        from .page_writer import build_template_args
        return build_template_args(self, k, v, i, the_prefixed, validated_aroi_domains)

    def _write_pages_parallel(self, k, sorted_values, template, output_path, the_prefixed, start_time):
        """Parallel page generation using fork()."""
        from .page_writer import write_pages_parallel
        write_pages_parallel(self, k, sorted_values, template, output_path, the_prefixed, start_time)

    def write_relay_info(self):
        """Render and write per-relay HTML info documents to disk."""
        from .page_writer import write_relay_info
        write_relay_info(self)

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
        return calculate_uptime_display(relay)

    def _preformat_network_health_template_strings(self, health_metrics):
        """Pre-format all template strings to eliminate Jinja2 formatting overhead."""
        from .network_health import preformat_network_health_template_strings
        preformat_network_health_template_strings(health_metrics)

    def _calculate_network_health_metrics(self):
        """Calculate network health metrics. Delegates to network_health module."""
        from .network_health import calculate_network_health_metrics
        calculate_network_health_metrics(self)
