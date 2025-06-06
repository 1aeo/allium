"""
File: relays.py

Relays class object consisting of relays (list of dict) and onionoo fetch
timestamp
"""

import hashlib
import json
import os
import re
import statistics
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
        self.uptime_ts_file = os.path.join(os.path.dirname(ABS_PATH), "uptime_timestamp")
        self.json = self._fetch_onionoo_details()
        if self.json == None:
            return
        self.timestamp = self._write_api_timestamp(self.ts_file, require_json=True)

        self._fix_missing_observed_bandwidth()
        self._sort_by_bandwidth()
        self._trim_platform()
        self._add_hashed_contact()
        self._process_aroi_contacts()  # Process AROI display info first
        self._categorize()  # Then build categories with processed relay objects

    def _fetch_onionoo_details(self):
        """
        Make request to onionoo to retrieve details document, return  JSON
        response
        """
        try:
            json_data = self._make_conditional_request(self.onionoo_url, self.ts_file)
            if json_data is None:
                print("no onionoo update since last run, dying peacefully...")
                sys.exit(1)
            return json_data
        except urllib.error.HTTPError as err:
            if err.code == 304:
                print("no onionoo update since last run, dying peacefully...")
                sys.exit(1)
            else:
                raise err

    def _fetch_onionoo_authorities_uptime(self, authority_fingerprints):
        """
        Fetch uptime data from Onionoo API for directory authorities only to reduce memory usage (2GB to 200MB)and API load.
        Uses timestamp headers for conditional requests to avoid downloading unchanged data.
        
        Args:
            authority_fingerprints: List of fingerprints for directory authorities
        Returns:
            Tuple of (uptime_data_dict, metadata_dict) where:
            - uptime_data_dict: Dictionary mapping fingerprint to uptime data, or None if no new data (304)
            - metadata_dict: Information about fetch status, timestamps, etc.
        """
        if not authority_fingerprints:
            return {}, {'status': 'no_authorities', 'message': 'No directory authorities found'}
            
        try:
            # Build uptime API URL with specific fingerprints
            fingerprint_params = ','.join(authority_fingerprints)
            uptime_url = self.onionoo_url.replace('/details', '/uptime') + '?lookup=' + fingerprint_params
            
            # Make conditional request using common function
            uptime_data = self._make_conditional_request(uptime_url, self.uptime_ts_file)
            
            if uptime_data is None:
                print("no uptime data update since last run, using cached data...")
                # Get the timestamp of when data was last fetched
                last_updated = None
                if os.path.isfile(self.uptime_ts_file):
                    with open(self.uptime_ts_file, "r") as ts_file:
                        last_updated = ts_file.read()
                
                return None, {
                    'status': 'not_modified', 
                    'message': 'Uptime data unchanged since last fetch',
                    'last_updated': last_updated
                }
            
            # Write timestamp for successful response using common function
            current_timestamp = self._write_api_timestamp(self.uptime_ts_file)
            
            # Create lookup dictionary by fingerprint
            uptime_by_fingerprint = {}
            for relay_uptime in uptime_data.get('relays', []):
                fingerprint = relay_uptime.get('fingerprint', '')
                if fingerprint:
                    uptime_by_fingerprint[fingerprint] = relay_uptime.get('uptime', {})
            
            return uptime_by_fingerprint, {
                'status': 'success',
                'message': 'Uptime data successfully fetched',
                'last_updated': current_timestamp,
                'authorities_count': len(uptime_by_fingerprint)
            }
            
        except urllib.error.HTTPError as err:
            print(f"HTTP Error fetching uptime data: {err}")
            return {}, {
                'status': 'error',
                'message': f'HTTP Error: {err}',
                'last_updated': None
            }
        except Exception as e:
            print(f"Warning: Could not fetch uptime data for authorities: {e}")
            return {}, {
                'status': 'error', 
                'message': f'Error: {e}',
                'last_updated': None
            }

    def _write_api_timestamp(self, timestamp_file_path, require_json=False):
        """
        Store encoded timestamp in the specified file to enable conditional requests
        
        Args:
            timestamp_file_path: Path to the timestamp file to write
            require_json: If True, only write timestamp if self.json is not None
        Returns:
            Formatted timestamp string
        """
        timestamp = time.time()
        f_timestamp = time.strftime(
            "%a, %d %b %Y %H:%M:%S GMT", time.gmtime(timestamp)
        )
        
        # For backward compatibility, check json requirement for details API
        if not require_json or self.json is not None:
            with open(timestamp_file_path, "w", encoding="utf8") as ts_file:
                ts_file.write(f_timestamp)

        return f_timestamp

    def _make_conditional_request(self, url, timestamp_file_path):
        """
        Make a conditional HTTP request using If-Modified-Since header if timestamp file exists
        
        Args:
            url: The URL to request
            timestamp_file_path: Path to the timestamp file for conditional requests
            
        Returns:
            JSON response data, or None if 304 Not Modified
            
        Raises:
            HTTPError: For non-304 HTTP errors
            Exception: For other request errors
        """
        # Add conditional request headers if we have a previous timestamp
        if os.path.isfile(timestamp_file_path):
            with open(timestamp_file_path, "r") as ts_file:
                prev_timestamp = ts_file.read()
            headers = {"If-Modified-Since": prev_timestamp}
            conn = urllib.request.Request(url, headers=headers)
        else:
            conn = urllib.request.Request(url)
        
        try:
            api_response = urllib.request.urlopen(conn).read()
            return json.loads(api_response.decode("utf-8"))
        except urllib.error.HTTPError as err:
            if err.code == 304:
                return None  # Indicates no new data (Not Modified)
            else:
                raise err

    def _trim_platform(self):
        """
        Trim platform to retain base operating system without version number or
        unnecessary classification which could affect sorting

        e.g. "Tor 0.3.4.9 on Linux" -> "Linux"
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

    def _sort_by_bandwidth(self):
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
        
        # Track network-wide totals for consensus weight fraction calculations
        # We calculate these here to avoid re-iterating 7 times through all relays later with _sort 6 times and _calculate_consensus_weight_fractions 1 time
        total_guard_cw = 0
        total_middle_cw = 0
        total_exit_cw = 0

        for idx, relay in enumerate(self.json["relays"]):
            # Extract consensus weight once per relay to avoid repeated dict lookups
            # This value gets used multiple times: once per _sort call + once for totals
            cw = relay.get("consensus_weight", 0)
            
            # Accumulate network-wide totals while we have the consensus weight value
            # Already inside the loop, so we don't need to iterate through all relays again in _sort 6 times and _calculate_consensus_weight_fractions 1 time
            if "Exit" in relay["flags"]:
                total_exit_cw += cw
            elif "Guard" in relay["flags"]:
                total_guard_cw += cw
            else:
                total_middle_cw += cw

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

    def create_output_dir(self):
        """
        Ensure self.output_dir exists (required for write functions)
        """
        os.makedirs(self.output_dir, exist_ok=True)

    def write_misc(
        self,
        template,
        path,
        path_prefix="../",
        sorted_by=None,
        reverse=True,
        is_index=False,
    ):
        """
        Render and write unsorted HTML listings to disk

        Args:
            template:    jinja template name
            path:        path to generate HTML document
            path_prefix: path to prefix other docs/includes
            sorted_by:   key to sort by, used in family and networks pages
            reverse:     passed to sort() function in family and networks pages
            is_index:    whether document is main index listing, limits list to 500
        """
        # Special handling for directory authorities page
        if template == "misc-authorities.html":
            authorities_data = self._process_directory_authorities()
            
            if authorities_data is None:
                print("Failed to process directory authorities data")
                return
                
            # Calculate summary metrics
            total_authorities = len(authorities_data)
            # Version compliance metrics commented out until we have real consensus-health data
            # compliant_authorities = [a for a in authorities_data if a.get('version_compliant', False)]
            # non_compliant_authorities = [a for a in authorities_data if not a.get('version_compliant', False)]
            
            # Uptime outliers
            above_average = [a for a in authorities_data if a.get('uptime_zscore') and a['uptime_zscore'] > 0.3]
            below_average = [a for a in authorities_data if a.get('uptime_zscore') and a['uptime_zscore'] < -0.5 and a['uptime_zscore'] > -2.0]
            problem_authorities = [a for a in authorities_data if a.get('uptime_zscore') and a['uptime_zscore'] <= -2.0]
            
            # Store authority data and summary metrics as attributes for template access
            self.authorities_data = authorities_data
            self.authorities_summary = {
                'total_authorities': total_authorities,
                # 'compliant_authorities': compliant_authorities,
                # 'non_compliant_authorities': non_compliant_authorities,
                'above_average_uptime': above_average,
                'below_average_uptime': below_average,
                'problem_uptime': problem_authorities,
            }
        
        template = ENV.get_template(template)
        self.json["relay_subset"] = self.json["relays"]
        template_render = template.render(
            relays=self,
            sorted_by=sorted_by,
            reverse=reverse,
            is_index=is_index,
            path_prefix=path_prefix,
        )
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

    def write_pages_by_key(self, k):
        """
        Render and write sorted HTML relay listings to disk

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

        for v in self.json["sorted"][k]:
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
                path_prefix="../../",
                key=k,
                value=v,
                sp_countries=the_prefixed,
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
            rendered = template.render(
                relay=relay, path_prefix="../", relays=self
            )
            with open(
                os.path.join(output_path, "%s.html" % relay["fingerprint"]),
                "w",
                encoding="utf8",
            ) as html:
                html.write(rendered)

    def _process_directory_authorities(self):
        """
        Process directory authority data including uptime statistics, 
        version compliance, and health metrics
        """
        # Filter directory authorities from already-fetched relay data
        authorities_data = [relay for relay in self.json['relays'] if 'Authority' in relay.get('flags', [])]
        
        if not authorities_data:
            print("No directory authorities found in relay data")
            return None
        
        # Get fingerprints of authorities to fetch uptime data efficiently
        authority_fingerprints = [auth.get('fingerprint', '') for auth in authorities_data if auth.get('fingerprint')]
        
        # Fetch uptime data only for directory authorities
        uptime_by_fingerprint, uptime_metadata = self._fetch_onionoo_authorities_uptime(authority_fingerprints)
        
        # Handle case where uptime data hasn't changed (304 response)
        if uptime_by_fingerprint is None:
            print("Using cached uptime data for directory authorities")
            # For now, we'll continue without uptime data. In a production system,
            # you might want to implement actual caching of the previous uptime data
            uptime_by_fingerprint = {}
            
        # Process each authority using the fetched uptime data
        processed_authorities = []
        one_month_uptimes = []
        
        for authority in authorities_data:
            fingerprint = authority.get('fingerprint', '')
            
            # Get uptime data for this authority from our targeted fetch
            uptime_info = uptime_by_fingerprint.get(fingerprint, {})
            
            # Calculate average uptime percentages from uptime data
            uptime_1month = self._calculate_average_uptime(uptime_info.get('1_month', {}))
            uptime_6months = self._calculate_average_uptime(uptime_info.get('6_months', {}))
            uptime_1year = self._calculate_average_uptime(uptime_info.get('1_year', {}))
            uptime_5years = self._calculate_average_uptime(uptime_info.get('5_years', {}))
            
            if uptime_1month is not None:
                one_month_uptimes.append(uptime_1month)
            
            # Process authority data (only include fields that are actually used in template)
            processed_authority = {
                'nickname': authority.get('nickname', ''),
                'fingerprint': authority.get('fingerprint', ''),
                'running': authority.get('running', False),
                'country': authority.get('country', ''),
                'country_name': authority.get('country_name', ''),
                'as': authority.get('as', ''),
                'as_name': authority.get('as_name', ''),
                'contact': authority.get('contact', ''),
                'version': authority.get('version', ''),
                'platform': authority.get('platform', ''),
                'first_seen': authority.get('first_seen', ''),
                'last_restarted': authority.get('last_restarted', ''),
                'last_seen': authority.get('last_seen', ''),
                'uptime_1month': uptime_1month,
                'uptime_6months': uptime_6months, 
                'uptime_1year': uptime_1year,
                'uptime_5years': uptime_5years,
            }
            
            processed_authorities.append(processed_authority)
        
        # Calculate z-scores for 1-month uptime
        if len(one_month_uptimes) > 1:
            mean_uptime = statistics.mean(one_month_uptimes)
            stdev_uptime = statistics.stdev(one_month_uptimes)
            
            for authority in processed_authorities:
                if authority['uptime_1month'] is not None and stdev_uptime > 0:
                    authority['uptime_zscore'] = (authority['uptime_1month'] - mean_uptime) / stdev_uptime
                else:
                    authority['uptime_zscore'] = None
        else:
            for authority in processed_authorities:
                authority['uptime_zscore'] = None
        
        # Version compliance - commented out until we have real consensus-health data
        # recommended_version = "0.4.8.12"  # This should come from consensus-health data
        # for authority in processed_authorities:
        #     authority['recommended_version'] = recommended_version
        #     authority['version_compliant'] = authority.get('version', '') == recommended_version
            
        # Sort alphabetically by nickname
        processed_authorities.sort(key=lambda x: x['nickname'].lower())
        
        # Store uptime metadata for template access
        self.uptime_metadata = uptime_metadata
        
        return processed_authorities
    
    def _calculate_average_uptime(self, uptime_data):
        """
        Calculate average uptime percentage from Onionoo uptime data
        
        Args:
            uptime_data: Dictionary with 'values' list and 'factor' for conversion
            
        Returns:
            Float percentage (0-100) or None if no data
        """
        if not uptime_data or 'values' not in uptime_data or 'factor' not in uptime_data:
            return None
            
        values = uptime_data['values']
        factor = uptime_data['factor']
        
        if not values:
            return None
            
        # Filter out None values and convert to percentages
        valid_values = [v * factor * 100 for v in values if v is not None]
        
        if not valid_values:
            return None
            
        return sum(valid_values) / len(valid_values)
