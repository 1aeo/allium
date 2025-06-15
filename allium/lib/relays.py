"""
File: relays.py

Relays class object consisting of relays (list of dict) and onionoo fetch
timestamp
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from shutil import rmtree
from jinja2 import Environment, FileSystemLoader
from .aroileaders import _calculate_aroi_leaderboards
from .progress import log_progress, get_memory_usage

ABS_PATH = os.path.dirname(os.path.abspath(__file__))
ENV = Environment(
    loader=FileSystemLoader(os.path.join(ABS_PATH, "../templates")),
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=True  # Enable autoescape to prevent XSS vulnerabilities
)


class Relays:
    """Relay class consisting of processing routines and onionoo data"""

    def __init__(self, output_dir, onionoo_url, relay_data, use_bits=False, progress=False, start_time=None, progress_step=0, total_steps=34):
        self.output_dir = output_dir
        self.onionoo_url = onionoo_url
        self.use_bits = use_bits
        self.progress = progress
        self.start_time = start_time or time.time()
        self.progress_step = progress_step
        self.total_steps = total_steps
        self.ts_file = os.path.join(os.path.dirname(ABS_PATH), "timestamp")
        
        # Use provided relay data (fetched by coordinator)
        self.json = relay_data
        if self.json is None:
            return
        
        # Generate timestamp for compatibility
        self.timestamp = time.strftime(
            "%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time())
        )

        self._fix_missing_observed_bandwidth()
        self._sort_by_observed_bandwidth()
        self._trim_platform()
        self._add_hashed_contact()
        self._process_aroi_contacts()  # Process AROI display info first
        self._preprocess_template_data()  # Pre-compute template optimization data
        self._categorize()  # Then build categories with processed relay objects
        self._generate_aroi_leaderboards()  # Generate AROI operator leaderboards
        self._generate_smart_context()  # Generate intelligence analysis

    def _log_progress(self, message, increment_step=False):
        """Log progress message using shared progress utility"""
        # Note: increment_step parameter is kept for backwards compatibility but not used
        log_progress(message, self.start_time, self.progress_step, self.total_steps, self.progress)



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

    def _fix_missing_observed_bandwidth(self):
        """
        Set the observed_bandwidth parameter value for any relay missing the
        parameter to 0; the observed_bandwidth parameter is (apparently)
        optional, I hadn't run into an instance of it missing until 2019-10-03

        "[...] Missing if router descriptor containing this information cannot be
        found."
        --https://metrics.torproject.org/onionoo.html#details_relay_observed_bandwidth

        """
        for idx, relay in enumerate(self.json["relays"]):
            if not relay.get("observed_bandwidth"):
                self.json["relays"][idx]["observed_bandwidth"] = 0

    def _simple_aroi_parsing(self, contact):
        """
        Extract AROI domain from contact information if conditions are met.
        For display purposes only - does not affect the stored/hashed contact info.
        More details: https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/
        
        Args:
            contact: The contact string to process
        Returns:
            AROI domain string or empty string if no AROI detected
        """
        if not contact:
            return "none"
            
        # Check if both required patterns are present
        url_match = re.search(r'url:(?:https?://)?([^,\s]+)', contact)
        ciiss_match = 'ciissversion:2' in contact
        
        if url_match and ciiss_match:
            # Extract domain and clean it up
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
        Adds a hashed contact key/value for every relay
        """
        for idx, relay in enumerate(self.json["relays"]):
            contact = relay.get("contact", "")
            # Hash the original contact info
            self.json["relays"][idx]["contact_md5"] = hashlib.md5(contact.encode("utf-8")).hexdigest()

    def _preprocess_template_data(self):
        """
        Pre-process data for template rendering optimization.
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
        import html
        
        for relay in self.json["relays"]:
            # Optimization 1: Pre-escape contact strings (19.95% savings)
            if relay.get("contact"):
                relay["contact_escaped"] = html.escape(relay["contact"])
            else:
                relay["contact_escaped"] = ""
                
            # Optimization 2: Pre-escape and lowercase flag strings (40.8% combined savings)
            if relay.get("flags"):
                relay["flags_escaped"] = [html.escape(flag) for flag in relay["flags"]]
                relay["flags_lower_escaped"] = [html.escape(flag.lower()) for flag in relay["flags"]]
            else:
                relay["flags_escaped"] = []
                relay["flags_lower_escaped"] = []
                
            # Optimization 3: Pre-split first_seen dates (used multiple times)
            if relay.get("first_seen"):
                relay["first_seen_date"] = relay["first_seen"].split(' ', 1)[0]
                relay["first_seen_date_escaped"] = html.escape(relay["first_seen_date"])
            else:
                relay["first_seen_date"] = ""
                relay["first_seen_date_escaped"] = ""
                
            # Optimization 4: Pre-compute percentage values for relay-info templates
            # This avoids expensive format operations in individual relay pages
            if relay.get("consensus_weight_fraction") is not None:
                relay["consensus_weight_percentage"] = f"{relay['consensus_weight_fraction'] * 100:.2f}%"
            else:
                relay["consensus_weight_percentage"] = "N/A"
                
            if relay.get("guard_probability") is not None:
                relay["guard_probability_percentage"] = f"{relay['guard_probability'] * 100:.2f}%"
            else:
                relay["guard_probability_percentage"] = "N/A"
                
            if relay.get("middle_probability") is not None:
                relay["middle_probability_percentage"] = f"{relay['middle_probability'] * 100:.2f}%"
            else:
                relay["middle_probability_percentage"] = "N/A"
                
            if relay.get("exit_probability") is not None:
                relay["exit_probability_percentage"] = f"{relay['exit_probability'] * 100:.2f}%"
            else:
                relay["exit_probability_percentage"] = "N/A"
                
            # Optimization 5: Pre-compute bandwidth formatting (major relay-list.html optimization)
            # This avoids calling _determine_unit and _format_bandwidth_with_unit in templates
            obs_bw = relay.get("observed_bandwidth", 0)
            obs_unit = self._determine_unit(obs_bw)
            obs_formatted = self._format_bandwidth_with_unit(obs_bw, obs_unit)
            relay["obs_bandwidth_formatted"] = obs_formatted
            relay["obs_bandwidth_unit"] = obs_unit
            relay["obs_bandwidth_with_unit"] = f"{obs_formatted} {obs_unit}"
            
            # Optimization 6: Pre-compute time ago formatting (expensive function calls)
            if relay.get("last_restarted"):
                relay["last_restarted_ago"] = self._format_time_ago(relay["last_restarted"])
                relay["last_restarted_date"] = relay["last_restarted"].split(' ', 1)[0]
            else:
                relay["last_restarted_ago"] = "unknown"
                relay["last_restarted_date"] = "unknown"
                
            # Optimization 7: Pre-parse IP addresses (string operations)
            if relay.get("or_addresses") and len(relay["or_addresses"]) > 0:
                relay["ip_address"] = relay["or_addresses"][0].split(':', 1)[0]
            else:
                relay["ip_address"] = "unknown"
                
            # Optimization 8: Pre-escape and truncate commonly used fields
            if relay.get("nickname"):
                relay["nickname_escaped"] = html.escape(relay["nickname"])
                relay["nickname_truncated"] = html.escape(relay["nickname"][:14])
            else:
                relay["nickname_escaped"] = "Unknown"
                relay["nickname_truncated"] = "Unknown"
                
            if relay.get("as_name"):
                relay["as_name_escaped"] = html.escape(relay["as_name"])
                relay["as_name_truncated"] = html.escape(relay["as_name"][:20])
            else:
                relay["as_name_escaped"] = "Unknown"
                relay["as_name_truncated"] = "Unknown"
                
            if relay.get("platform"):
                relay["platform_escaped"] = html.escape(relay["platform"])
                relay["platform_truncated"] = html.escape(relay["platform"][:10])
            else:
                relay["platform_escaped"] = "Unknown"
                relay["platform_truncated"] = "Unknown"
                
            # Optimization 9: Pre-escape AROI domain and other commonly used fields
            if relay.get("aroi_domain") and relay["aroi_domain"] != "none":
                relay["aroi_domain_escaped"] = html.escape(relay["aroi_domain"])
            else:
                relay["aroi_domain_escaped"] = "none"
                
            # Optimization 10: Pre-compute time formatting for relay-info pages
            if relay.get("first_seen"):
                relay["first_seen_ago"] = self._format_time_ago(relay["first_seen"])
            else:
                relay["first_seen_ago"] = "unknown"
                
            if relay.get("last_seen"):
                relay["last_seen_ago"] = self._format_time_ago(relay["last_seen"])
            else:
                relay["last_seen_ago"] = "unknown"
                
            # Optimization 11: Pre-compute uptime/downtime display based on last_restarted and Running flag
            relay["uptime_display"] = None
            if relay.get('last_restarted'):
                flags = relay.get('flags', [])
                is_running = 'Running' in flags
                
                # Calculate time difference from last_restarted to now using existing helper
                time_since_restart = self._format_time_ago(relay['last_restarted'])
                
                if time_since_restart and time_since_restart != "unknown":
                    if is_running:
                        relay["uptime_display"] = f"UP {time_since_restart}"
                    else:
                        relay["uptime_display"] = f"DOWN {time_since_restart}"
                else:
                    relay["uptime_display"] = "Unknown"
            else:
                relay["uptime_display"] = "Unknown"

    def _reprocess_uptime_data(self):
        """
        Reprocess uptime/downtime display for all relays.
        This method is kept for compatibility but now updates the uptime_display field.
        """
        for relay in self.json["relays"]:
            # Recalculate uptime/downtime display based on last_restarted and Running flag
            relay["uptime_display"] = None
            if relay.get('last_restarted'):
                flags = relay.get('flags', [])
                is_running = 'Running' in flags
                
                # Calculate time difference from last_restarted to now using existing helper
                time_since_restart = self._format_time_ago(relay['last_restarted'])
                
                if time_since_restart and time_since_restart != "unknown":
                    if is_running:
                        relay["uptime_display"] = f"UP {time_since_restart}"
                    else:
                        relay["uptime_display"] = f"DOWN {time_since_restart}"
                else:
                    relay["uptime_display"] = "Unknown"
            else:
                relay["uptime_display"] = "Unknown"

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
        f_timestamp = time.strftime(
            "%a, %d %b %Y %H:%M:%S GMT", time.gmtime(timestamp)
        )
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
        
        # Bandwidth measured tracking
        measured_relays = 0
        
        for relay in self.json['relays']:
            flags = relay.get('flags', [])
            consensus_weight = relay.get('consensus_weight', 0)
            
            is_guard = 'Guard' in flags
            is_exit = 'Exit' in flags
            
            # Count relays measured by >= 3 bandwidth authorities
            if relay.get('measured') is True:
                measured_relays += 1
            
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
            'exit_consensus_weight': total_exit_cw
        }
        
        return total_guard_cw, total_middle_cw, total_exit_cw

    def _sort(self, relay, idx, k, v, cw):
        """
        Populate self.sorted dictionary with values from :relay:

        Args:
            relay: relay from which values are derived
            idx:   index at which the relay can be found in self.json['relays']
            k:     the name of the key to use in self.sorted
            v:     the name of the subkey to use in self.sorted[k]
            cw:    consensus weight for this relay (passed to avoid repeated extraction)
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
        if relay.get("consensus_weight"):
            self.json["sorted"][k][v]["consensus_weight"] += relay["consensus_weight"]
        if relay.get("consensus_weight_fraction"):
            self.json["sorted"][k][v]["consensus_weight_fraction"] += float(relay["consensus_weight_fraction"])

        if k == "as":
            self.json["sorted"][k][v]["country"] = relay.get("country")
            self.json["sorted"][k][v]["country_name"] = relay.get("country")
            self.json["sorted"][k][v]["as_name"] = relay.get("as_name")

        if k == "family" or k == "contact" or k == "country" or k == "platform" or k == "as":
            # Families, contacts, countries, platforms, and networks benefit from additional tracking data:
            # - Contact info and MD5 hash for linking
            # - AROI domain for display purposes  
            # - Unique AS tracking for network diversity analysis
            # - First seen date tracking (oldest relay in group)
            # - For countries, platforms, and networks: also track unique contacts and families
            if k == "country" or k == "platform" or k == "as":
                # Track unique contacts and families for countries, platforms, and networks
                if not self.json["sorted"][k][v].get("unique_contact_set"):
                    self.json["sorted"][k][v]["unique_contact_set"] = set()
                if not self.json["sorted"][k][v].get("unique_family_set"):
                    self.json["sorted"][k][v]["unique_family_set"] = set()
                
                # Add this relay's contact hash to the country/platform/network's unique contacts
                c_str = relay.get("contact", "").encode("utf-8")
                c_hash = hashlib.md5(c_str).hexdigest()
                self.json["sorted"][k][v]["unique_contact_set"].add(c_hash)
                
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

            keys = ["as", "country", "platform"]
            for key in keys:
                # Pass consensus weight to avoid re-extracting it in _sort
                self._sort(relay, idx, key, relay.get(key), cw)

            for flag in relay["flags"]:
                self._sort(relay, idx, "flag", flag, cw)

            if relay.get("effective_family"):
                for member in relay["effective_family"]:
                    if not len(relay["effective_family"]) > 1:
                        continue
                    self._sort(relay, idx, "family", member, cw)

            self._sort(
                relay, idx, "first_seen", relay["first_seen"].split(" ")[0], cw
            )

            c_str = relay.get("contact", "").encode("utf-8")
            c_hash = hashlib.md5(c_str).hexdigest()
            self._sort(relay, idx, "contact", c_hash, cw)

        # Calculate consensus weight fractions using the totals we accumulated above
        # This avoids a second full iteration through all relays
        self._calculate_consensus_weight_fractions(total_guard_cw, total_middle_cw, total_exit_cw)
        
        # Calculate family statistics immediately after categorization when data is fresh
        # This calculates both network totals and family-specific statistics for misc-families pages
        self._calculate_and_cache_family_statistics(total_guard_cw, total_middle_cw, total_exit_cw)
        
        # Convert unique AS sets to counts for families, contacts, countries, platforms, and networks
        self._finalize_unique_as_counts()

    def _calculate_consensus_weight_fractions(self, total_guard_cw, total_middle_cw, total_exit_cw):
        """
        Calculate consensus weight fractions for guard, middle, and exit relays
        
        Args:
            total_guard_cw: Total consensus weight of all guard relays in the network
            total_middle_cw: Total consensus weight of all middle relays in the network  
            total_exit_cw: Total consensus weight of all exit relays in the network
            
        These totals are passed from _categorize to avoid re-iterating through all relays.
        """
        # Calculate fractions for each group using the provided network-wide totals
        for k in self.json["sorted"]:
            for v in self.json["sorted"][k]:
                item = self.json["sorted"][k][v]
                
                # Calculate fractions, avoiding division by zero
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
        
        # Process existing family structure for largest family size and large family count
        largest_family_size = 0
        large_family_count = 0
        
        if 'family' in self.json['sorted']:
            processed_fingerprints = set()
            
            # Process each family only once using deduplication
            for k, v in self.json['sorted']['family'].items():
                # Get first relay fingerprint to check if this family was already processed
                first_relay_idx = v['relays'][0]
                first_relay_fingerprint = self.json['relays'][first_relay_idx]['fingerprint']
                
                if first_relay_fingerprint not in processed_fingerprints:
                    # Track actual relay count and largest family
                    family_size = len(v['relays'])
                    largest_family_size = max(largest_family_size, family_size)
                    
                    # Count families with 10+ relays
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
            'large_family_count': large_family_count
        }

    def _finalize_unique_as_counts(self):
        """
        Convert unique AS sets to counts for families, contacts, countries, platforms, and networks and clean up memory.
        This should be called after all family, contact, country, platform, and network data has been processed.
        """
        for category in ["family", "contact", "country", "platform", "as"]:
            if category in self.json["sorted"]:
                for data in self.json["sorted"][category].values():
                    if "unique_as_set" in data:
                        data["unique_as_count"] = len(data["unique_as_set"])
                        # Remove the set to save memory and avoid JSON serialization issues
                        del data["unique_as_set"]
                    else:
                        # Fallback in case unique_as_set wasn't initialized
                        data["unique_as_count"] = 0
                    
                    # Handle country, platform, and network-specific unique counts
                    if category == "country" or category == "platform" or category == "as":
                        if "unique_contact_set" in data:
                            data["unique_contact_count"] = len(data["unique_contact_set"])
                            del data["unique_contact_set"]
                        else:
                            data["unique_contact_count"] = 0
                            
                        if "unique_family_set" in data:
                            data["unique_family_count"] = len(data["unique_family_set"])
                            del data["unique_family_set"]
                        else:
                            data["unique_family_count"] = 0

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
        self.json["relay_subset"] = self.json["relays"]
        
        # Handle page context and path prefix
        if page_ctx is None:
            page_ctx = {'path_prefix': '../'}  # default fallback
        
        # Pre-compute family statistics for misc-families templates
        template_vars = {
            "relays": self,
            "sorted_by": sorted_by,
            "reverse": reverse,
            "is_index": is_index,
            "page_ctx": page_ctx,
        }
        
        if template.name == "misc-families.html":
            family_stats = self.json.get('family_statistics', {
                'centralization_percentage': '0.0',
                'largest_family_size': 0,
                'large_family_count': 0
            })
            template_vars.update(family_stats)
        
        template_render = template.render(**template_vars)
        output = os.path.join(self.output_dir, path)
        os.makedirs(os.path.dirname(output), exist_ok=True)

        with open(output, "w", encoding="utf8") as html:
            html.write(template_render)

    def _determine_unit(self, bandwidth_bytes):
        """Determine unit - simple threshold checking"""
        if self.use_bits:
            bits = bandwidth_bytes * 8
            if bits >= 1000000000: # If greater than or equal to 1 Gbit/s
                return "Gbit/s"
            elif bits >= 1000000: # If greater than or equal to 1 Mbit/s
                return "Mbit/s"
            else:
                return "Kbit/s"
        else:
            if bandwidth_bytes >= 1000000000: # If greater than or equal to 1 GB/s
                return "GB/s"
            elif bandwidth_bytes >= 1000000: # If greater than or equal to 1 MB/s
                return "MB/s"
            else:
                return "KB/s"

    def _get_divisor_for_unit(self, unit):
        """Simple dictionary lookup for divisors"""
        divisors = {
            # Bits (convert bytes to bits, then to unit)
            "Gbit/s": 125000000,   # 1000000000 / 8
            "Mbit/s": 125000,      # 1000000 / 8  
            "Kbit/s": 125,         # 1000 / 8
            # Bytes  
            "GB/s": 1000000000,
            "MB/s": 1000000,
            "KB/s": 1000
        }
        if unit in divisors:
            return divisors[unit]
        raise ValueError(f"Unknown unit: {unit}")

    def _format_bandwidth_with_unit(self, bandwidth_bytes, unit, decimal_places=2):
        """Format bandwidth using specified unit with configurable decimal places"""
        divisor = self._get_divisor_for_unit(unit)
        value = bandwidth_bytes / divisor
        return f"{value:.{decimal_places}f}"

    def _format_time_ago(self, timestamp_str):
        """Format timestamp as multi-unit time ago (e.g., '2y 3m 2w ago')"""
        from datetime import datetime, timezone
        
        try:
            # Parse the timestamp string
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            timestamp = timestamp.replace(tzinfo=timezone.utc)
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

    def get_detail_page_context(self, category, value):
        """Generate page context with correct breadcrumb data for detail pages"""
        # Import here to avoid circular imports
        from allium import get_page_context
        
        mapping = {
            'as': ('as_detail', {'as_number': value}),
            'contact': ('contact_detail', {'contact_hash': value}),
            'country': ('country_detail', {'country_name': value}),
            'family': ('family_detail', {'family_hash': value}),
            'platform': ('platform_detail', {'platform_name': value}),
            'first_seen': ('first_seen_detail', {'date': value}),
            'flag': ('flag_detail', {'flag_name': value}),
        }
        breadcrumb_type, breadcrumb_data = mapping.get(category, (f"{category}_detail", {}))
        return get_page_context('detail', breadcrumb_type, breadcrumb_data)

    def write_pages_by_key(self, k):
        """
        Render and write sorted HTML relay listings to disk
        
        Optimizes family pages by pre-computing math calculations and string formatting
        while keeping Jinja2 template structure intact.
        Reducing overall compute time from 60s to 20s.
        
        """
        
        start_time = time.time()
        self._log_progress(f"Starting {k} page generation...")
        
        template = ENV.get_template(k + ".html")
        output_path = os.path.join(self.output_dir, k)

        # the "royal the" must be gramatically recognized
        the_prefixed = [
            "Dominican Republic",
            "Ivory Coast",
            "Marshall Islands",
            "Northern Marianas Islands",
            "Solomon Islands",
            "United Arab Emirates",
            "United Kingdom",
            "United States",
            "United States of America",
            "Vatican City",
            "Czech Republic",
            "Bahamas",
            "Gambia",
            "Netherlands",
            "Philippines",
            "Seychelles",
            "Sudan",
            "Ukraine",
        ]

        if os.path.exists(output_path):
            rmtree(output_path)

        # Sort first_seen pages by date to show oldest dates first
        if k == "first_seen":
            sorted_values = sorted(self.json["sorted"][k].keys())
        else:
            sorted_values = self.json["sorted"][k].keys()
        
        page_count = 0
        render_time = 0
        io_time = 0
        
        for v in sorted_values:
            i = self.json["sorted"][k][v]
            members = []

            for m_relay in i["relays"]:
                members.append(self.json["relays"][m_relay])
            if k == "flag":
                dir_path = os.path.join(output_path, v.lower())
            else:
                dir_path = os.path.join(output_path, v)

            os.makedirs(dir_path)
            self.json["relay_subset"] = members
            
            bandwidth_unit = self._determine_unit(i["bandwidth"])
            # Format all bandwidth values using the same unit
            bandwidth = self._format_bandwidth_with_unit(i["bandwidth"], bandwidth_unit)
            guard_bandwidth = self._format_bandwidth_with_unit(i["guard_bandwidth"], bandwidth_unit)
            middle_bandwidth = self._format_bandwidth_with_unit(i["middle_bandwidth"], bandwidth_unit)
            exit_bandwidth = self._format_bandwidth_with_unit(i["exit_bandwidth"], bandwidth_unit)
            
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
            
            # Generate page context with correct breadcrumb data
            page_ctx = self.get_detail_page_context(k, v)
            
            # Generate contact rankings for AROI leaderboards (only for contact pages)
            contact_rankings = []
            operator_reliability = None
            contact_display_data = None
            if k == "contact":
                contact_rankings = self._generate_contact_rankings(v)
                # Calculate operator reliability statistics
                operator_reliability = self._calculate_operator_reliability(v, members)
                # Pre-compute all contact-specific display data
                contact_display_data = self._compute_contact_display_data(
                    i, bandwidth_unit, operator_reliability, v, members
                )
            
            # Time the template rendering
            render_start = time.time()
            rendered = template.render(
                relays=self,
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
                network_position=network_position_display,
                is_index=False,
                page_ctx=page_ctx,
                key=k,
                value=v,
                sp_countries=the_prefixed,
                contact_rankings=contact_rankings,  # AROI leaderboard rankings for this contact
                operator_reliability=operator_reliability,  # Operator reliability statistics for contact pages
                contact_display_data=contact_display_data,  # Pre-computed contact-specific display data
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
                has_typed_relays=i["guard_count"] > 0 or i["middle_count"] > 0 or i["exit_count"] > 0
            )
            render_time += time.time() - render_start

            # Time the file I/O
            io_start = time.time()
            with open(
                os.path.join(dir_path, "index.html"), "w", encoding="utf8"
            ) as html:
                html.write(rendered)
            io_time += time.time() - io_start
            
            page_count += 1
            
            # Print progress for large page sets
            if page_count % 1000 == 0:
                self._log_progress(f"Processed {page_count} {k} pages...")

        end_time = time.time()
        total_time = end_time - start_time
        
        # Log completion and statistics with standard format
        self._log_progress(f"{k} page generation complete - Generated {page_count} pages in {total_time:.2f}s")
        if self.progress:
            # Additional detailed stats (not in standard format, but supporting info)
            print(f"    🎨 Template render time: {render_time:.2f}s ({render_time/total_time*100:.1f}%)")
            print(f"    💾 File I/O time: {io_time:.2f}s ({io_time/total_time*100:.1f}%)")
            if page_count > 0:
                print(f"    ⚡ Average per page: {total_time/page_count*1000:.1f}ms")
            print("---")

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
            # Import here to avoid circular imports
            from allium import get_page_context
            
            page_ctx = get_page_context('detail', 'relay_detail', {
                'nickname': relay.get('nickname', relay.get('fingerprint', 'Unknown')),
                'fingerprint': relay.get('fingerprint', 'Unknown'),
                'as_number': relay.get('as', '')
            })
            
            rendered = template.render(
                relay=relay, page_ctx=page_ctx, relays=self
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
        category_info = {
            'bandwidth': {'name': 'Bandwidth Champion', 'emoji': '🚀', 'title': 'Bandwidth Champion'},
                    'consensus_weight': {'name': 'Network Heavyweight', 'emoji': '⚖️', 'title': 'Network Heavyweight'},
        'exit_authority': {'name': 'Exit Heavyweight Master', 'emoji': '🚪', 'title': 'Exit Heavyweight Master'},
        'exit_operators': {'name': 'Exit Champion', 'emoji': '🚪', 'title': 'Exit Champion'},
        'guard_operators': {'name': 'Guard Gatekeepers', 'emoji': '🛡️', 'title': 'Guard Gatekeepers'},
            'most_diverse': {'name': 'Diversity Master', 'emoji': '🌈', 'title': 'Diversity Master'},
            'platform_diversity': {'name': 'Platform Hero', 'emoji': '💻', 'title': 'Platform Hero'},
            'non_eu_leaders': {'name': 'Non-EU Leader', 'emoji': '🌍', 'title': 'Non-EU Leader'},
            'frontier_builders': {'name': 'Frontier Builder', 'emoji': '🏴‍☠️', 'title': 'Frontier Builder'},
            'network_veterans': {'name': 'Network Veteran', 'emoji': '🏆', 'title': 'Network Veteran'},
            'reliability_masters': {'name': 'Reliability Master', 'emoji': '⏰', 'title': 'Reliability Master'},
            'legacy_titans': {'name': 'Legacy Titan', 'emoji': '👑', 'title': 'Legacy Titan'}
        }
        
        return category_info.get(category, {'name': category.replace('_', ' ').title(), 'emoji': '🏅', 'title': category.replace('_', ' ').title()})

    def _calculate_operator_reliability(self, contact_hash, operator_relays):
        """
        Calculate comprehensive reliability statistics for an operator.
        
        Uses shared uptime utilities to avoid code duplication with aroileaders.py.
        
        Args:
            contact_hash (str): Contact hash for the operator
            operator_relays (list): List of relay objects for this operator
            
        Returns:
            dict: Reliability statistics including overall uptime, time periods, and outliers
        """
        if not hasattr(self, 'uptime_data') or not self.uptime_data or not operator_relays:
            return None
            
        from .uptime_utils import extract_relay_uptime_for_period, calculate_statistical_outliers
        import statistics
        
        # Available time periods from Onionoo uptime API
        time_periods = ['1_month', '3_months', '6_months', '1_year', '5_years']
        period_display_names = {
            '1_month': '30d',
            '3_months': '90d', 
            '6_months': '6mo',
            '1_year': '1y',
            '5_years': '5y'
        }
        
        reliability_stats = {
            'overall_uptime': {},  # Unweighted average uptime per time period
            'relay_uptimes': [],   # Individual relay uptime data
            'outliers': {          # Statistical outliers (2+ std dev from mean)
                'low_outliers': [],
                'high_outliers': []
            },
            'valid_relays': 0,
            'total_relays': len(operator_relays)
        }
        
        # Process each time period using shared utilities
        all_relay_data = {}
        
        for period in time_periods:
            # Extract uptime data for this period using shared utility
            period_result = extract_relay_uptime_for_period(operator_relays, self.uptime_data, period)
            
            if period_result['uptime_values']:
                mean_uptime = statistics.mean(period_result['uptime_values'])
                std_dev = statistics.stdev(period_result['uptime_values']) if len(period_result['uptime_values']) > 1 else 0
                
                reliability_stats['overall_uptime'][period] = {
                    'average': mean_uptime,
                    'std_dev': std_dev,
                    'display_name': period_display_names[period],
                    'relay_count': len(period_result['uptime_values'])
                }
                
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
                            'uptime_periods': {}
                        }
                    all_relay_data[fingerprint]['uptime_periods'][period] = relay_data['uptime']
        
        # Set relay uptimes and valid relays count
        reliability_stats['relay_uptimes'] = list(all_relay_data.values())
        reliability_stats['valid_relays'] = len(all_relay_data)
        
        # Remove duplicate outliers (same relay appearing in multiple periods)
        # Keep the one with highest deviation
        def deduplicate_outliers(outliers):
            relay_outliers = {}
            for outlier in outliers:
                fp = outlier['fingerprint']
                if fp not in relay_outliers or outlier['deviation'] > relay_outliers[fp]['deviation']:
                    relay_outliers[fp] = outlier
            return list(relay_outliers.values())
        
        reliability_stats['outliers']['low_outliers'] = deduplicate_outliers(reliability_stats['outliers']['low_outliers'])
        reliability_stats['outliers']['high_outliers'] = deduplicate_outliers(reliability_stats['outliers']['high_outliers'])
        
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
            guard_bw = self._format_bandwidth_with_unit(i["guard_bandwidth"], bandwidth_unit)
            if guard_bw != '0.00':
                bw_components.append(f"{guard_bw} {bandwidth_unit} guard")
        
        if i["middle_count"] > 0 and i["middle_bandwidth"] > 0:
            middle_bw = self._format_bandwidth_with_unit(i["middle_bandwidth"], bandwidth_unit)
            if middle_bw != '0.00':
                bw_components.append(f"{middle_bw} {bandwidth_unit} middle")
        
        if i["exit_count"] > 0 and i["exit_bandwidth"] > 0:
            exit_bw = self._format_bandwidth_with_unit(i["exit_bandwidth"], bandwidth_unit)
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
                intelligence_formatted['performance_underutilized_fps'] = contact_intel.get('performance_underutilized_fps', [])
                intelligence_formatted['maturity'] = contact_intel.get('maturity', '')
        
        display_data['operator_intelligence'] = intelligence_formatted
        
        # 4. Overall uptime formatting with green highlighting
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
        
        # 5. Outliers calculations and formatting
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
                outliers_data['tooltip'] = f"6 month: ≥2σ {two_sigma_threshold:.1f}% from average μ {mean_uptime:.1f}%"
                
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
        
        # 6. Uptime data timestamp (reuse existing uptime data)
        uptime_timestamp = None
        if hasattr(self, 'uptime_data') and self.uptime_data and self.uptime_data.get('relays_published'):
            uptime_timestamp = self.uptime_data['relays_published']
        display_data['uptime_timestamp'] = uptime_timestamp
        
        # 7. Real-time downtime alerts (idea #8 from uptime integration proposals)
        downtime_alerts = self._calculate_operator_downtime_alerts(v, members, i, bandwidth_unit)
        display_data['downtime_alerts'] = downtime_alerts
        
        return display_data

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
            'total_offline_bandwidth_formatted': self._format_bandwidth_with_unit(total_offline_bandwidth, bandwidth_unit),
            'offline_bandwidth_percentage': offline_bandwidth_percentage,
            'total_operator_bandwidth_formatted': self._format_bandwidth_with_unit(operator_total_bandwidth, bandwidth_unit)
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
