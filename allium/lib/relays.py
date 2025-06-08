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

ABS_PATH = os.path.dirname(os.path.abspath(__file__))
ENV = Environment(
    loader=FileSystemLoader(os.path.join(ABS_PATH, "../templates")),
    trim_blocks=True,
    lstrip_blocks=True,
)


class Relays:
    """Relay class consisting of processing routines and onionoo data"""

    def __init__(self, output_dir, onionoo_url, use_bits=False):
        self.output_dir = output_dir
        self.onionoo_url = onionoo_url
        self.use_bits = use_bits
        self.ts_file = os.path.join(os.path.dirname(ABS_PATH), "timestamp")
        self.json = self._fetch_onionoo_details()
        if self.json == None:
            return
        self.timestamp = self._write_timestamp()

        self._fix_missing_observed_bandwidth()
        self._sort_by_observed_bandwidth()
        self._trim_platform()
        self._add_hashed_contact()
        self._process_aroi_contacts()  # Process AROI display info first
        self._categorize()  # Then build categories with processed relay objects
        self._generate_smart_context()  # Generate intelligence analysis

    def _fetch_onionoo_details(self):
        """
        Make request to onionoo to retrieve details document, return  JSON
        response
        """
        if os.path.isfile(self.ts_file):
            with open(self.ts_file, "r") as ts_file:
                prev_timestamp = ts_file.read()
            headers = {"If-Modified-Since": prev_timestamp}
            conn = urllib.request.Request(self.onionoo_url, headers=headers)
        else:
            conn = urllib.request.Request(self.onionoo_url)

        try:
            api_response = urllib.request.urlopen(conn).read()
        except urllib.error.HTTPError as err:
            if err.code == 304:
                print("no onionoo update since last run, dying peacefully...")
                sys.exit(1)
            else:
                raise (err)

        return json.loads(api_response.decode("utf-8"))

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

    def _generate_smart_context(self):
        """Generate smart context intelligence analysis"""
        try:
            from intelligence_engine import IntelligenceEngine
        except ImportError:
            from .intelligence_engine import IntelligenceEngine
        
        print("[Intelligence] Starting Tier 1 analysis...")
        engine = IntelligenceEngine(self.json)
        self.json['smart_context'] = engine.analyze_all_layers()
        print("[Intelligence] Tier 1 analysis complete")

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

    def _format_bandwidth_with_unit(self, bandwidth_bytes, unit):
        """Format bandwidth using specified unit"""
        divisor = self._get_divisor_for_unit(unit)
        value = bandwidth_bytes / divisor
        return f"{value:.2f}"

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
        
        For family pages, moves expensive operations from Jinja2 to Python:
        - Percentage calculations (consensus_weight_fraction * 100, etc.)
        - Pluralization logic ("relay" vs "relays")
        - Complex conditional logic for punctuation

        Args:
            k: onionoo key to sort by (as, country, platform...)
        """
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
                
            # Generate page context with correct breadcrumb data
            page_ctx = self.get_detail_page_context(k, v)
            
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
                is_index=False,
                page_ctx=page_ctx,
                key=k,
                value=v,
                sp_countries=the_prefixed,
                # Family page optimizations - pre-computed values to avoid expensive Jinja2 operations
                **({"consensus_weight_percentage": f"{i['consensus_weight_fraction'] * 100:.2f}%",
                    "guard_consensus_weight_percentage": f"{i['guard_consensus_weight_fraction'] * 100:.2f}%",
                    "middle_consensus_weight_percentage": f"{i['middle_consensus_weight_fraction'] * 100:.2f}%",
                    "exit_consensus_weight_percentage": f"{i['exit_consensus_weight_fraction'] * 100:.2f}%",
                    "guard_relay_text": "guard relay" if i["guard_count"] == 1 else "guard relays",
                    "middle_relay_text": "middle relay" if i["middle_count"] == 1 else "middle relays",
                    "exit_relay_text": "exit relay" if i["exit_count"] == 1 else "exit relays",
                    "has_guard": i["guard_count"] > 0,
                    "has_middle": i["middle_count"] > 0,
                    "has_exit": i["exit_count"] > 0,
                    "has_typed_relays": i["guard_count"] > 0 or i["middle_count"] > 0 or i["exit_count"] > 0}
                   if k == "family" else {})
            )

            with open(
                os.path.join(dir_path, "index.html"), "w", encoding="utf8"
            ) as html:
                html.write(rendered)

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

    def _finalize_unique_as_counts(self):
        """
        Convert unique AS sets to counts for families, contacts, countries, platforms, and networks
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
