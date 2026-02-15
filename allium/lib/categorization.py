"""
File: categorization.py

Relay sorting, categorization, consensus weight fractions, family statistics,
AS rarity scoring, contact derived data, and display value precomputation.
Extracted from relays.py for better modularity.
"""

import re

from .string_utils import extract_contact_display_name


def calculate_network_totals(relay_set):
    """
    Calculate network totals using three different relay counting methodologies:
    - Primary: Each relay counted once, Exit prioritized over Guard > Middle
    - Categories: Each relay counted once with separate Guard+Exit category  
    - All: Count relays in multiple roles (multi-role relays increment multiple counters)
    
    Returns consensus weight totals for backward compatibility.
    Caches all three count types in relay_set.json['network_totals'].
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
    
    for relay in relay_set.json['relays']:
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
    total_relays = len(relay_set.json['relays'])
    primary_counts["total"] = total_relays
    categories_counts["total"] = total_relays
    all_counts["total"] = total_relays
    
    # Cache all counting methods for template access
    relay_set.json['network_totals'] = {
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

def sort_relay(relay_set, relay, idx, k, v, cw, cw_fraction):
    """
    Populate self.sorted dictionary with values from :relay:

    Args:
        relay: relay from which values are derived
        idx:   index at which the relay can be found in relay_set.json['relays']
        k:     the name of the key to use in self.sorted
        v:     the name of the subkey to use in self.sorted[k]
        cw:    consensus weight for this relay (passed to avoid repeated extraction)
        cw_fraction: consensus weight fraction (API value preferred, computed fallback)
    """
    if not v or not re.match(r"^[A-Za-z0-9_-]+$", v):
        return

    if not k in relay_set.json["sorted"]:
        relay_set.json["sorted"][k] = dict()

    if not v in relay_set.json["sorted"][k]:
        relay_set.json["sorted"][k][v] = {
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
            relay_set.json["sorted"][k][v]["country_counts"] = {}

    bw = relay["observed_bandwidth"]
    # Use the consensus weight passed from _categorize (no repeated dict lookup)
    relay_set.json["sorted"][k][v]["relays"].append(idx)
    relay_set.json["sorted"][k][v]["bandwidth"] += bw

    if "Exit" in relay["flags"]:
        relay_set.json["sorted"][k][v]["exit_count"] += 1
        relay_set.json["sorted"][k][v]["exit_bandwidth"] += bw
        relay_set.json["sorted"][k][v]["exit_consensus_weight"] += cw
    elif "Guard" in relay["flags"]:
        relay_set.json["sorted"][k][v]["guard_count"] += 1
        relay_set.json["sorted"][k][v]["guard_bandwidth"] += bw
        relay_set.json["sorted"][k][v]["guard_consensus_weight"] += cw
    else:
        relay_set.json["sorted"][k][v]["middle_count"] += 1
        relay_set.json["sorted"][k][v]["middle_bandwidth"] += bw
        relay_set.json["sorted"][k][v]["middle_consensus_weight"] += cw

    # Add consensus weight tracking
    # Accumulate both raw consensus_weight and the fraction (API or computed)
    if relay.get("consensus_weight"):
        relay_set.json["sorted"][k][v]["consensus_weight"] += relay["consensus_weight"]
    # Accumulate fraction - uses API value when available, computed fallback otherwise
    relay_set.json["sorted"][k][v]["consensus_weight_fraction"] += cw_fraction

    if k == "as":
        # relay["country"] is already UPPERCASE from _preprocess_template_data()
        relay_set.json["sorted"][k][v]["country"] = relay.get("country")
        relay_set.json["sorted"][k][v]["country_name"] = relay.get("country_name") or relay.get("country", "")
        relay_set.json["sorted"][k][v]["as_name"] = relay.get("as_name")
    
    if k == "country":
        # Set country name for countries - truncate to 32 characters as requested
        # relay["country"] is already UPPERCASE from _preprocess_template_data()
        full_country_name = relay.get("country_name") or relay.get("country", "")
        truncated_country_name = full_country_name[:32] if len(full_country_name) > 32 else full_country_name
        relay_set.json["sorted"][k][v]["country_name"] = truncated_country_name
        relay_set.json["sorted"][k][v]["country_name_full"] = full_country_name

    if k in ("family", "contact", "country", "platform", "as"):
        # Families, contacts, countries, platforms, and networks benefit from additional tracking data:
        # - Contact info and MD5 hash for linking
        # - AROI domain for display purposes  
        # - Unique AS tracking for network diversity analysis
        # - First seen date tracking (oldest relay in group)
        # - For countries, platforms, and networks: also track unique contacts and families
        if k in ("country", "platform", "as"):
            # Track unique contacts, families, and AROI domains for countries, platforms, and networks
            if not relay_set.json["sorted"][k][v].get("unique_contact_set"):
                relay_set.json["sorted"][k][v]["unique_contact_set"] = set()
            if not relay_set.json["sorted"][k][v].get("unique_family_set"):
                relay_set.json["sorted"][k][v]["unique_family_set"] = set()
            if not relay_set.json["sorted"][k][v].get("unique_aroi_set"):
                relay_set.json["sorted"][k][v]["unique_aroi_set"] = set()
            if not relay_set.json["sorted"][k][v].get("aroi_to_contact_map"):
                relay_set.json["sorted"][k][v]["aroi_to_contact_map"] = {}
            
            # Add this relay's contact hash to the country/platform/network's unique contacts
            # Use the pre-computed contact_md5 which includes unified AROI domain grouping
            c_hash = relay.get("contact_md5", "")
            if c_hash:
                relay_set.json["sorted"][k][v]["unique_contact_set"].add(c_hash)
            
            # Add this relay's AROI domain to the country/platform/network's unique AROI domains
            aroi_domain = relay.get("aroi_domain", "")
            if aroi_domain and aroi_domain != "none" and aroi_domain.strip():
                relay_set.json["sorted"][k][v]["unique_aroi_set"].add(aroi_domain)
                # APPROACH 1 ENHANCEMENT: Build AROI-to-contact mapping during categorization
                relay_set.json["sorted"][k][v]["aroi_to_contact_map"][aroi_domain] = c_hash
            
            # Add this relay's family to the country/platform/network's unique families
            if relay.get("effective_family") and len(relay["effective_family"]) > 1:
                # Use the first family member as the family identifier
                family_id = relay["effective_family"][0]
                relay_set.json["sorted"][k][v]["unique_family_set"].add(family_id)
        if k in ("family", "contact", "as"):
            # Count measured relays
            if relay.get("measured"):
                relay_set.json["sorted"][k][v]["measured_count"] += 1 
        
        relay_set.json["sorted"][k][v]["contact"] = relay.get("contact", "")
        relay_set.json["sorted"][k][v]["contact_md5"] = relay.get("contact_md5", "")
        relay_set.json["sorted"][k][v]["aroi_domain"] = relay.get("aroi_domain", "")
        
        # Track country counts for contacts (primary country calculation)
        # relay["country"] is already UPPERCASE from _preprocess_template_data()
        if k == "contact" and (country := relay.get("country")):
            relay_set.json["sorted"][k][v]["country_counts"][country] = \
                relay_set.json["sorted"][k][v]["country_counts"].get(country, 0) + 1

        # Track unique AS numbers for this family/contact/country/platform/network
        relay_as = relay.get("as")
        if relay_as:
            relay_set.json["sorted"][k][v]["unique_as_set"].add(relay_as)

        # update the first_seen parameter to always contain the oldest
        # relay's first_seen date
        if not relay_set.json["sorted"][k][v].get("first_seen"):
            relay_set.json["sorted"][k][v]["first_seen"] = relay["first_seen"]
        elif relay_set.json["sorted"][k][v]["first_seen"] > relay["first_seen"]:
            relay_set.json["sorted"][k][v]["first_seen"] = relay["first_seen"]

def categorize(relay_set):
    """
    Iterate over relay_set.json['relays'] set and call sort_relay(relay_set, ) against
    discovered relays with attributes we use to generate static sets
    """
    relay_set.json["sorted"] = dict()
    
    # Initialize all expected categories to prevent template errors with small datasets
    expected_categories = ["as", "country", "platform", "flag", "family", "first_seen", "contact"]
    for category in expected_categories:
        relay_set.json["sorted"][category] = dict()
    
    # Calculate comprehensive network totals once - replaces duplicate calculations
    total_guard_cw, total_middle_cw, total_exit_cw = calculate_network_totals(relay_set)

    for idx, relay in enumerate(relay_set.json["relays"]):
        # Extract consensus weight once per relay to avoid repeated dict lookups
        # This value gets used multiple times: once per _sort call + once for totals
        cw = relay.get("consensus_weight", 0)
        
        # Get relay's consensus weight fraction - prefer API value, fallback to computed
        # This ensures consistency with individual relay display
        api_fraction = relay.get("consensus_weight_fraction")
        if api_fraction is not None:
            cw_fraction = api_fraction
        elif hasattr(relay_set, '_total_network_cw') and relay_set._total_network_cw > 0:
            cw_fraction = cw / relay_set._total_network_cw
        else:
            cw_fraction = 0.0

        # Sort by AS, country (already UPPERCASE from _preprocess_template_data), and platform
        sort_relay(relay_set, relay, idx, "as", relay.get("as"), cw, cw_fraction)
        sort_relay(relay_set, relay, idx, "country", relay.get("country"), cw, cw_fraction)
        sort_relay(relay_set, relay, idx, "platform", relay.get("platform"), cw, cw_fraction)

        for flag in relay["flags"]:
            sort_relay(relay_set, relay, idx, "flag", flag, cw, cw_fraction)

        if relay.get("effective_family"):
            for member in relay["effective_family"]:
                if not len(relay["effective_family"]) > 1:
                    continue
                sort_relay(relay_set, relay, idx, "family", member, cw, cw_fraction)

        sort_relay(relay_set, 
            relay, idx, "first_seen", relay["first_seen"].split(" ")[0], cw, cw_fraction
        )

        # Use the pre-computed contact_md5 which includes unified AROI domain grouping
        c_hash = relay.get("contact_md5", "")
        sort_relay(relay_set, relay, idx, "contact", c_hash, cw, cw_fraction)

    # Calculate consensus weight fractions using the totals we accumulated above
    # This avoids a second full iteration through all relays
    calculate_consensus_weight_fractions(relay_set, total_guard_cw, total_middle_cw, total_exit_cw)
    
    # Calculate family statistics immediately after categorization when data is fresh
    # This calculates both network totals and family-specific statistics for misc-families pages
    calculate_and_cache_family_statistics(relay_set, total_guard_cw, total_middle_cw, total_exit_cw)
    
    # Convert unique AS sets to counts for families, contacts, countries, platforms, and networks
    finalize_unique_as_counts(relay_set)
    
    # Calculate derived contact data: primary countries and bandwidth means
    calculate_contact_derived_data(relay_set)
    
    # PERF OPTIMIZATION: Pre-compute display values to eliminate expensive Jinja2 calculations
    # This pre-computes formatted bandwidth, consensus weight, and relay count strings
    # for all sorted groups, reducing template render time by 30-40%
    precompute_display_values(relay_set)
    
    # NOTE: _precompute_all_contact_page_data() is called from the coordinator
    # AFTER uptime data, bandwidth data, and AROI leaderboards are processed.
    # This is required because contact page data depends on those calculations.

def calculate_consensus_weight_fractions(relay_set, total_guard_cw, total_middle_cw, total_exit_cw):
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
    for k in relay_set.json["sorted"]:
        for v in relay_set.json["sorted"][k]:
            item = relay_set.json["sorted"][k][v]
            
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

def calculate_and_cache_family_statistics(relay_set, total_guard_cw, total_middle_cw, total_exit_cw):
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
    for relay in relay_set.json['relays']:
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
    total_relay_count = len(relay_set.json['relays'])
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
        
        for relay in relay_set.json['relays']:
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
    
    if 'family' in relay_set.json['sorted']:
        processed_fingerprints = set()
        
        # Process each family only once using deduplication (serves multiple metrics)
        for k, v in relay_set.json['sorted']['family'].items():
            # Get first relay fingerprint to check if this family was already processed
            first_relay_idx = v['relays'][0]
            first_relay_fingerprint = relay_set.json['relays'][first_relay_idx]['fingerprint']
            
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
                    relay_fingerprint = relay_set.json['relays'][r]['fingerprint']
                    processed_fingerprints.add(relay_fingerprint)
    
    # Cache enhanced family statistics
    relay_set.json['family_statistics'] = {
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

def finalize_unique_as_counts(relay_set):
    """
    Convert unique AS sets to counts for families, contacts, countries, platforms, and networks and clean up memory.
    This should be called after all family, contact, country, platform, and network data has been processed.
    """
    from .country_utils import calculate_as_rarity_score as _as_rarity_score, assign_as_rarity_tier as _as_rarity_tier, compute_as_cw_thresholds
    # Compute dynamic CW thresholds once from the AS data
    _cw_thresholds = compute_as_cw_thresholds(relay_set.json.get('sorted', {}).get('as', {}))
    for category in ["family", "contact", "country", "platform", "as"]:
        if category in relay_set.json["sorted"]:
            for key, data in relay_set.json["sorted"][category].items():
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
                                if relay_set.base_url and hasattr(relay_set, 'validated_aroi_domains') and aroi in relay_set.validated_aroi_domains:
                                    aroi_contact_html_items.append(f'<a href="{relay_set.base_url}/{aroi.lower()}/">{aroi}</a>')
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

def propagate_as_rarity(relay_set):
    """Propagate pre-computed AS rarity data from sorted['as'] to each relay dict."""
    as_data = relay_set.json.get('sorted', {}).get('as', {})
    _empty = {}
    for relay in relay_set.json['relays']:
        e = as_data.get(relay.get('as', ''), _empty)
        relay['as_rarity_score'] = e.get('as_rarity_score', 0)
        relay['as_rarity_tier'] = e.get('as_rarity_tier', 'common')
        relay['as_operator_count'] = e.get('unique_contact_count', 0)
        cw = e.get('consensus_weight_fraction', 0)
        relay['as_cw_label'] = f"{cw * 100:.2f}%" if cw >= 0.0005 else ("<0.05%" if cw > 0 else "0%")

def calculate_contact_derived_data(relay_set):
    """
    Calculate derived contact data: primary countries and bandwidth means in single pass.
    Optimized implementation combining both calculations for better performance.
    """
    if "contact" not in relay_set.json["sorted"]:
        return
        
    for contact_hash, contact_data in relay_set.json["sorted"]["contact"].items():
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
                country = relay_set.json["relays"][relay_idx].get("country")
                if country and country not in country_names:
                    country_names[country] = relay_set.json["relays"][relay_idx].get("country_name") or country
            
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
            unit = relay_set.bandwidth_formatter.determine_unit(mean_bandwidth)
            formatted_mean = relay_set.bandwidth_formatter.format_bandwidth_with_unit(mean_bandwidth, unit)
            contact_data["bandwidth_mean_display"] = f"{formatted_mean} {unit}"
        else:
            # Handle edge case of no relays
            contact_data["bandwidth_mean"] = 0
            fallback_unit = "KB/s" if not relay_set.use_bits else "Kbit/s"
            contact_data["bandwidth_mean_display"] = f"0.00 {fallback_unit}"

def precompute_display_values(relay_set):
    """
    PERF: Pre-compute display strings for misc listing pages (30-40% speedup).
    Used by misc-families.html, misc-contacts.html, misc-networks.html, etc.
    """
    fmt = relay_set.bandwidth_formatter  # Alias for brevity
    
    for category in ["family", "contact", "as", "country", "platform", "flag"]:
        if category not in relay_set.json["sorted"]:
            continue
            
        for key, data in relay_set.json["sorted"][category].items():
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


