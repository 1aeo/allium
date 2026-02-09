"""
Country and Geographic Utilities for Allium

Centralized country logic and geographic categorization functions.
Single source of truth for all country-related analysis across the application.

NOTE: All country codes are stored in UPPERCASE format to match RouteFluxMap's URL schema.
"""

# === CORE REGIONAL MAPPING ===
# Source: intelligence_engine.py _calculate_regional_hhi_detailed()
CORE_REGIONS = {
    'north_america': {'US', 'CA', 'MX'},
    'europe': {'DE', 'FR', 'GB', 'NL', 'IT', 'ES', 'SE', 'NO', 'DK', 'FI', 'CH', 'AT', 'BE', 'IE', 'PT'},
    'asia_pacific': {'JP', 'AU', 'NZ', 'KR', 'SG', 'HK', 'TW', 'TH', 'MY', 'PH'},
    'eastern_europe': {'RU', 'UA', 'PL', 'CZ', 'HU', 'RO', 'BG', 'SK', 'HR', 'SI', 'EE', 'LV', 'LT'},
}

# === EU DEFINITIONS ===
# Geographic Europe (subset) - matches intelligence_engine.py 'europe' region
EU_GEOGRAPHIC_REGION = {'DE', 'FR', 'GB', 'NL', 'IT', 'ES', 'SE', 'NO', 'DK', 'FI', 'CH', 'AT', 'BE', 'IE', 'PT'}

# EU Political Union (superset) - comprehensive EU membership
# Source: aroileaders.py eu_countries definition
EU_POLITICAL_REGION = {
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 
    'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 
    'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
}

# === FRONTIER/RARE COUNTRIES ===
# Source: aroileaders.py rare_countries definition
FRONTIER_COUNTRIES = {'MN', 'TN', 'UY', 'KZ', 'MD', 'LK', 'MK', 'MT'}

# === WEIGHTED RARE COUNTRY SCORING SYSTEM ===
# Multi-factor scoring for dynamic rare country classification

# Geopolitical Classifications
GEOPOLITICAL_CLASSIFICATIONS = {
    # Conflict zones (3 points) - Active conflicts, post-conflict zones
    'conflict_zones': {
        'SY', 'YE', 'AF', 'MM', 'SD', 'SO', 'LY', 'IQ', 'ML', 'CF', 'SS', 
        'TD', 'NI', 'HT', 'PK', 'NG'
    },
    
    # Authoritarian regimes (3 points) - Freedom House "Not Free"
    'authoritarian': {
        'CN', 'IR', 'KP', 'SA', 'BY', 'TM', 'UZ', 'LA', 'VN', 'CU', 'ER',
        'AZ', 'BH', 'CM', 'DJ', 'GQ', 'TJ', 'EG'
    },
    
    # Island nations (2 points) - Strategic geographic positions
    'island_nations': {
        'MT', 'CY', 'IS', 'MV', 'FJ', 'MG', 'MU', 'SC', 'BB', 'JM', 'TT',
        'BH', 'BN', 'KI', 'TV', 'TO', 'WS', 'VU', 'SB', 'PW', 'FM',
        'MH', 'NR', 'AG', 'BS', 'DM', 'GD', 'KN', 'LC', 'VC', 'CV'
    },
    
    # Landlocked developing (2 points) - UN LDC + landlocked countries
    'landlocked_developing': {
        'AF', 'BF', 'BI', 'CF', 'TD', 'KZ', 'KG', 'TJ', 'TM', 'UZ', 'BT',
        'NP', 'PY', 'BO', 'ML', 'NE', 'RW', 'UG', 'ZM', 'ZW', 'MW', 'LS',
        'SZ', 'AW'
    },
    
    # General developing (1 point) - World Bank Lower/Lower-middle income
    'developing': {
        # Africa
        'DZ', 'AO', 'BJ', 'BW', 'CM', 'CG', 'CI', 'EG', 'ET', 'GA', 'GH',
        'GN', 'KE', 'LR', 'LY', 'MA', 'MZ', 'NA', 'NG', 'SN', 'SL', 'TZ', 
        'TN', 'ZA', 'ZM', 'ZW',
        # Asia
        'BD', 'IN', 'ID', 'LK', 'MN', 'PK', 'PH', 'TH', 'VN',
        # Latin America  
        'AR', 'BR', 'CL', 'CO', 'EC', 'PE', 'UY', 'VE', 'MX', 'GT', 'HN',
        'SV', 'CR', 'PA', 'DO', 'JM',
        # Eastern Europe
        'AL', 'BA', 'MK', 'MD', 'ME'
    }
}

# Regional Classifications
REGIONAL_CLASSIFICATIONS = {
    # Underrepresented regions (2 points) - Regions with typically low relay counts
    'underrepresented': {
        # Africa
        'DZ', 'AO', 'BJ', 'BW', 'BF', 'BI', 'CM', 'CV', 'CF', 'TD', 'KM',
        'CG', 'CI', 'DJ', 'EG', 'GQ', 'ER', 'ET', 'GA', 'GM', 'GH', 'GN',
        'GW', 'KE', 'LS', 'LR', 'LY', 'MG', 'MW', 'ML', 'MR', 'MU', 'MA',
        'MZ', 'NA', 'NE', 'NG', 'RW', 'ST', 'SN', 'SC', 'SL', 'SO', 'ZA',
        'SS', 'SD', 'SZ', 'TZ', 'TG', 'TN', 'UG', 'ZM', 'ZW',
        
        # Central Asia
        'KZ', 'KG', 'TJ', 'TM', 'UZ',
        
        # Pacific Islands
        'FJ', 'KI', 'MH', 'FM', 'NR', 'PW', 'PG', 'WS', 'SB', 'TO', 'TV', 'VU'
    },
    
    # Emerging regions (1 point) - Growing but still underrepresented
    'emerging': {
        # Caribbean
        'AG', 'BS', 'BB', 'BZ', 'DM', 'DO', 'GD', 'GY', 'HT', 'JM', 'KN',
        'LC', 'VC', 'SR', 'TT',
        
        # Central America
        'CR', 'SV', 'GT', 'HN', 'NI', 'PA',
        
        # South Asia
        'BD', 'BT', 'MV', 'NP', 'LK',
        
        # Southeast Asia (emerging)
        'BN', 'KH', 'LA', 'MM', 'TL'
    }
}

# === UTILITY FUNCTIONS ===

def get_country_region(country_code):
    """
    Determine which region a country belongs to.
    
    Args:
        country_code (str): 2-letter country code (case insensitive)
        
    Returns:
        str: Region name ('north_america', 'europe', 'asia_pacific', 'eastern_europe', 'other')
    """
    country_upper = country_code.upper()
    
    for region, countries in CORE_REGIONS.items():
        if country_upper in countries:
            return region
    
    return 'other'

def get_regional_distribution(countries):
    """
    Analyze regional distribution of a list of countries.
    
    Args:
        countries (list): List of 2-letter country codes
        
    Returns:
        dict: Regional distribution with counts and metadata
    """
    regional_presence = {region: 0 for region in CORE_REGIONS.keys()}
    regional_presence['other'] = 0
    
    for country in countries:
        region = get_country_region(country)
        regional_presence[region] += 1
    
    # Calculate metadata
    active_regions = sum(1 for count in regional_presence.values() if count > 0)
    dominant_region = max(regional_presence.items(), key=lambda x: x[1])
    
    return {
        'distribution': regional_presence,
        'active_regions': active_regions,
        'dominant_region': dominant_region[0],
        'dominant_count': dominant_region[1],
        'total_countries': len(countries)
    }

def is_eu_political(country_code):
    """Check if country is in EU political union."""
    return country_code.upper() in EU_POLITICAL_REGION

def is_eu_geographic(country_code):
    """Check if country is in geographic Europe region."""
    return country_code.upper() in EU_GEOGRAPHIC_REGION

def is_frontier_country(country_code):
    """Check if country is classified as frontier/rare."""
    return country_code.upper() in FRONTIER_COUNTRIES

def count_non_eu_countries(countries, use_political=True):
    """
    Count countries that are not in EU.
    
    Args:
        countries (list): List of country codes
        use_political (bool): Use political EU definition (default) vs geographic
        
    Returns:
        int: Number of non-EU countries
    """
    eu_set = EU_POLITICAL_REGION if use_political else EU_GEOGRAPHIC_REGION
    return sum(1 for country in countries if country.upper() not in eu_set)



def calculate_geographic_achievement(countries):
    """
    Calculate dynamic geographic achievement based on operator's country distribution.
    
    Args:
        countries (list): List of 2-letter country codes
        
    Returns:
        str: Achievement title based on geographic distribution
    """
    if not countries:
        return "Regional Specialist"
    
    distribution = get_regional_distribution(countries)
    
    # Multi-continental operators (3+ regions)
    if distribution['active_regions'] >= 3:
        if distribution['total_countries'] >= 8:
            return "Global Emperor"
        else:
            return "Multi-Continental Champion"
    
    # Single region dominance
    elif distribution['dominant_count'] > 0:
        region_name = distribution['dominant_region']
        country_count = distribution['dominant_count']
        
        # Region-specific titles based on country count
        if region_name == 'north_america':
            return "North America Emperor" if country_count >= 3 else "North America Champion"
        elif region_name == 'europe':
            return "Europe Emperor" if country_count >= 5 else "Europe Champion"
        elif region_name == 'asia_pacific':
            return "Asia-Pacific Emperor" if country_count >= 4 else "Asia-Pacific Champion"
        elif region_name == 'eastern_europe':
            return "Eastern Europe Emperor" if country_count >= 3 else "Eastern Europe Champion"
        elif region_name == 'other':
            return "Frontier Emperor" if country_count >= 3 else "Frontier Pioneer"
    
    # Fallback
    return "Regional Specialist"

def calculate_diversity_score(countries, platforms=None, unique_as_count=None,
                              as_diversity_score=None):
    """
    Calculate standardized diversity score.
    
    Weights: Country (3.0) > AS rarity (2.0 normalized) > Platform (1.0)
    
    Args:
        countries (list): List of country codes
        platforms (list, optional): List of platform types
        unique_as_count (int, optional): Number of unique ASNs (used for AS calc + fallback)
        as_diversity_score (float, optional): Sum of AS rarity scores across unique AS
    
    Returns:
        float: Weighted diversity score
    """
    diversity_score = 0.0
    
    # Geographic component — highest weight (countries x 3.0)
    if countries:
        diversity_score += len(countries) * 3.0
    
    # Network component — middle weight (AS rarity / 2.5)
    # Equivalent to: unique_as_count * (avg_rarity / 5) * 2.0 — the count cancels out
    if as_diversity_score is not None and unique_as_count and unique_as_count > 0:
        diversity_score += as_diversity_score / 2.5
    elif unique_as_count:
        diversity_score += unique_as_count * 1.0
    
    # Platform component — lowest weight (platforms x 1.0)
    if platforms:
        diversity_score += len(platforms) * 1.0
    
    return diversity_score


# === AS DIVERSITY SCORING ===

def calculate_as_rarity_score(as_cw_fraction, unique_contact_count):
    """
    AS rarity score: CW base (0-3) + contact bonus (0-2) = 0-5.
    
    CW base: how much of the network's authority does this AS hold?
    Contact bonus: how unique is the hosting choice?
    
    Args:
        as_cw_fraction (float): Consensus weight fraction (0.0 to 1.0)
        unique_contact_count (int): Number of distinct contacts in this AS
    
    Returns:
        int: 0-5 rarity score
    """
    cw_pct = as_cw_fraction * 100
    # CW base (0-3)
    if cw_pct >= 5.0:     base = 0   # Dominant (≥5% of network CW)
    elif cw_pct >= 0.5:   base = 1   # Major (0.5% – 5%)
    elif cw_pct >= 0.05:  base = 2   # Moderate (0.05% – 0.5%)
    elif cw_pct > 0:      base = 3   # Small (<0.05%)
    else:                 base = 0   # Unmeasured
    # Contact bonus (0-2)
    if unique_contact_count <= 0:    bonus = 0   # Unknown
    elif unique_contact_count == 1:  bonus = 2   # Sole operator
    elif unique_contact_count <= 10: bonus = 1   # Few operators
    else:                            bonus = 0   # Popular (10+)
    return base + bonus


def assign_as_rarity_tier(rarity_score):
    """
    Tier assignment on 0-5 scale.
    
    Args:
        rarity_score (int): AS rarity score (0-5)
    
    Returns:
        str: Tier name ('legendary', 'epic', 'rare', 'emerging', 'common')
    """
    if rarity_score >= 4:    return 'legendary'
    elif rarity_score >= 3:  return 'epic'
    elif rarity_score >= 2:  return 'rare'
    elif rarity_score >= 1:  return 'emerging'
    else:                    return 'common'


def calculate_operator_as_diversity_score(operator_relays, sorted_as_data):
    """
    Calculate the sum of AS rarity scores across an operator's unique AS numbers.
    
    Args:
        operator_relays (list): List of relay dicts for one operator
        sorted_as_data (dict): The sorted['as'] dict with pre-computed as_rarity_score
        
    Returns:
        float: Sum of AS rarity scores (0 if no data)
    """
    if not operator_relays or not sorted_as_data:
        return 0.0
    
    seen_as = set()
    total_score = 0.0
    
    for relay in operator_relays:
        as_number = relay.get('as', '')
        if not as_number or as_number in seen_as:
            continue
        seen_as.add(as_number)
        
        # Look up pre-computed AS rarity score (keys match relay['as'] format)
        as_entry = sorted_as_data.get(as_number)
        if as_entry:
            total_score += as_entry.get('as_rarity_score', 0)
    
    return total_score

def calculate_relay_count_factor(country_relay_count):
    """
    Calculate scoring factor based on relay count.
    
    For AROI operators, we only evaluate countries where operators actually have relays,
    so the minimum meaningful count is 1 relay.
    
    Args:
        country_relay_count (int): Number of relays in country
        
    Returns:
        int: Points (6 for 1 relay, 5 for 2 relays, etc., min 0)
    """
    if country_relay_count == 0:
        # This shouldn't happen in AROI context, but handle gracefully
        return 0
    return max(7 - country_relay_count, 0)

def calculate_network_percentage_factor(country_relays, total_network_relays):
    """
    Calculate scoring factor based on network percentage.
    
    Args:
        country_relays (int): Number of relays in country
        total_network_relays (int): Total relays in network
        
    Returns:
        int: Points based on network percentage thresholds
    """
    if total_network_relays == 0:
        return 0
        
    percentage = (country_relays / total_network_relays) * 100
    
    if percentage < 0.05:    return 6  # Ultra-rare (<0.05%)
    elif percentage < 0.1:   return 4  # Very rare (0.05-0.1%)
    elif percentage < 0.2:   return 2  # Rare (0.1-0.2%)
    else:                    return 0  # Common (>0.2%)

def calculate_geopolitical_factor(country_code):
    """
    Calculate scoring factor based on geopolitical significance.
    
    Args:
        country_code (str): 2-letter country code
        
    Returns:
        int: Points based on geopolitical classification
    """
    country_upper = country_code.upper()
    
    if country_upper in GEOPOLITICAL_CLASSIFICATIONS['conflict_zones']:
        return 3
    elif country_upper in GEOPOLITICAL_CLASSIFICATIONS['authoritarian']:
        return 3
    elif country_upper in GEOPOLITICAL_CLASSIFICATIONS['island_nations']:
        return 2
    elif country_upper in GEOPOLITICAL_CLASSIFICATIONS['landlocked_developing']:
        return 2
    elif country_upper in GEOPOLITICAL_CLASSIFICATIONS['developing']:
        return 1
    else:
        return 0

def calculate_regional_factor(country_code):
    """
    Calculate scoring factor based on regional underrepresentation.
    
    Args:
        country_code (str): 2-letter country code
        
    Returns:
        int: Points based on regional classification
    """
    country_upper = country_code.upper()
    
    if country_upper in REGIONAL_CLASSIFICATIONS['underrepresented']:
        return 2
    elif country_upper in REGIONAL_CLASSIFICATIONS['emerging']:
        return 1
    else:
        return 0



def assign_rarity_tier(rarity_score):
    """
    Assign tier classification based on weighted rarity score.
    
    Args:
        rarity_score (int): Calculated rarity score
        
    Returns:
        str: Tier classification
    """
    if rarity_score >= 15:   return 'legendary'    # 🏆
    elif rarity_score >= 10: return 'epic'         # ⭐
    elif rarity_score >= 6:  return 'rare'         # 🎖️
    elif rarity_score >= 3:  return 'emerging'     # 📍
    else:                    return 'common'       # Standard




def count_frontier_countries_weighted_with_existing_data(countries, country_data, total_relays, min_score=6):
    """
    Ultra-optimized version that uses pre-calculated country data from relays.py.
    
    This is the most efficient implementation as it leverages existing work from relays.py
    categorization instead of re-scanning the entire relay dataset.
    
    Args:
        countries (list): List of country codes to evaluate
        country_data (dict): Pre-calculated country data from relays.json["sorted"]["country"]
        total_relays (int): Total number of relays in the network
        min_score (int): Minimum score to be considered rare
        
    Returns:
        int: Number of rare countries in the list
    """
    if not country_data or total_relays == 0:
        return 0  # No country data available, return 0 rare countries
    
    rare_count = 0
    for country in countries:
        if country:
            country_upper = country.upper()
            
            # Get relay count from existing country data (zero-cost lookup)
            country_relays = 0
            if country_upper in country_data:
                country_relays = len(country_data[country_upper].get('relays', []))
            
            # Calculate factors efficiently without any relay scanning
            relay_count_factor = calculate_relay_count_factor(country_relays)
            network_percentage_factor = calculate_network_percentage_factor(country_relays, total_relays)
            geopolitical_factor = calculate_geopolitical_factor(country)
            regional_factor = calculate_regional_factor(country)
            
            # Apply weighted formula
            rarity_score = (
                (relay_count_factor * 4) +
                (network_percentage_factor * 3) +
                (geopolitical_factor * 2) +
                (regional_factor * 1)
            )
            
            if rarity_score >= min_score:
                rare_count += 1
    
    return rare_count

def get_rare_countries_weighted_with_existing_data(country_data, total_relays, min_score=6):
    """
    Ultra-optimized version that uses pre-calculated country data from relays.py.
    
    This is the most efficient implementation for getting all rare countries in the network
    as it leverages existing work from relays.py categorization.
    
    Args:
        country_data (dict): Pre-calculated country data from relays.json["sorted"]["country"]
        total_relays (int): Total number of relays in the network
        min_score (int): Minimum score to be considered rare
        
    Returns:
        set: Set of rare country codes
    """
    if not country_data or total_relays == 0:
        return set()  # No country data available, return empty set
    
    rare_countries = set()
    
    # Process all countries in the country_data (countries with relays)
    for country_upper, data in country_data.items():
        country_relays = len(data.get('relays', []))
        
        # Calculate factors efficiently
        relay_count_factor = calculate_relay_count_factor(country_relays)
        network_percentage_factor = calculate_network_percentage_factor(country_relays, total_relays)
        geopolitical_factor = calculate_geopolitical_factor(country_upper)
        regional_factor = calculate_regional_factor(country_upper)
        
        # Apply weighted formula
        rarity_score = (
            (relay_count_factor * 4) +
            (network_percentage_factor * 3) +
            (geopolitical_factor * 2) +
            (regional_factor * 1)
        )
        
        if rarity_score >= min_score:
            rare_countries.add(country_upper)
    
    # Also check countries with 0 relays (geopolitically significant ones)
    # These are not in country_data but might still be rare due to geopolitical factors
    for country in GEOPOLITICAL_CLASSIFICATIONS.keys():
        if country not in country_data:
            # Country has 0 relays
            relay_count_factor = calculate_relay_count_factor(0)
            network_percentage_factor = calculate_network_percentage_factor(0, total_relays)
            geopolitical_factor = calculate_geopolitical_factor(country)
            regional_factor = calculate_regional_factor(country)
            
            rarity_score = (
                (relay_count_factor * 4) +
                (network_percentage_factor * 3) +
                (geopolitical_factor * 2) +
                (regional_factor * 1)
            )
            
            if rarity_score >= min_score:
                rare_countries.add(country)
    
    return rare_countries

# === REQUIRED FOR INTELLIGENCE ENGINE ===

def get_geographic_regions_for_analysis():
    """Return geographic regional mapping for intelligence analysis HHI calculations"""
    return CORE_REGIONS.copy()
