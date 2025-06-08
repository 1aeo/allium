"""
Country and Geographic Utilities for Allium

Centralized country logic and geographic categorization functions.
Single source of truth for all country-related analysis across the application.
"""

# === CORE REGIONAL MAPPING ===
# Source: intelligence_engine.py _calculate_regional_hhi_detailed()
CORE_REGIONS = {
    'north_america': {'us', 'ca', 'mx'},
    'europe': {'de', 'fr', 'gb', 'nl', 'it', 'es', 'se', 'no', 'dk', 'fi', 'ch', 'at', 'be', 'ie', 'pt'},
    'asia_pacific': {'jp', 'au', 'nz', 'kr', 'sg', 'hk', 'tw', 'th', 'my', 'ph'},
    'eastern_europe': {'ru', 'ua', 'pl', 'cz', 'hu', 'ro', 'bg', 'sk', 'hr', 'si', 'ee', 'lv', 'lt'},
}

# === EU DEFINITIONS ===
# Geographic Europe (subset) - matches intelligence_engine.py 'europe' region
EU_GEOGRAPHIC_REGION = {'de', 'fr', 'gb', 'nl', 'it', 'es', 'se', 'no', 'dk', 'fi', 'ch', 'at', 'be', 'ie', 'pt'}

# EU Political Union (superset) - comprehensive EU membership
# Source: aroileaders.py eu_countries definition
EU_POLITICAL_REGION = {
    'at', 'be', 'bg', 'hr', 'cy', 'cz', 'dk', 'ee', 'fi', 'fr', 
    'de', 'gr', 'hu', 'ie', 'it', 'lv', 'lt', 'lu', 'mt', 'nl', 
    'pl', 'pt', 'ro', 'sk', 'si', 'es', 'se'
}

# === FRONTIER/RARE COUNTRIES ===
# Source: aroileaders.py rare_countries definition
FRONTIER_COUNTRIES = {'mn', 'tn', 'uy', 'kz', 'md', 'lk', 'mk', 'mt', 'ee', 'lv'}

# === UTILITY FUNCTIONS ===

def get_country_region(country_code):
    """
    Determine which region a country belongs to.
    
    Args:
        country_code (str): 2-letter country code (case insensitive)
        
    Returns:
        str: Region name ('north_america', 'europe', 'asia_pacific', 'eastern_europe', 'other')
    """
    country_lower = country_code.lower()
    
    for region, countries in CORE_REGIONS.items():
        if country_lower in countries:
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
    return country_code.lower() in EU_POLITICAL_REGION

def is_eu_geographic(country_code):
    """Check if country is in geographic Europe region."""
    return country_code.lower() in EU_GEOGRAPHIC_REGION

def is_frontier_country(country_code):
    """Check if country is classified as frontier/rare."""
    return country_code.lower() in FRONTIER_COUNTRIES

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
    return sum(1 for country in countries if country.lower() not in eu_set)

def count_frontier_countries(countries):
    """Count frontier/rare countries in list."""
    return sum(1 for country in countries if is_frontier_country(country))

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

def calculate_diversity_score(countries, platforms=None, unique_as_count=None):
    """
    Calculate standardized diversity score.
    
    Args:
        countries (list): List of country codes
        platforms (list, optional): List of platform types
        unique_as_count (int, optional): Number of unique ASNs
        
    Returns:
        float: Weighted diversity score
    """
    diversity_score = 0.0
    
    # Geographic component (countries × 2.0)
    if countries:
        diversity_score += len(countries) * 2.0
    
    # Platform component (OS types × 1.5) 
    if platforms:
        diversity_score += len(platforms) * 1.5
    
    # Network component (unique ASNs × 1.0)
    if unique_as_count:
        diversity_score += unique_as_count * 1.0
    
    return diversity_score

# === LEGACY COMPATIBILITY ===

def get_standard_regions():
    """Return standard regional mapping for backward compatibility."""
    return CORE_REGIONS.copy()

def get_eu_countries():
    """Return EU political union countries for backward compatibility."""
    return EU_POLITICAL_REGION.copy()

def get_frontier_countries():
    """Return frontier country definitions for backward compatibility."""
    return FRONTIER_COUNTRIES.copy() 