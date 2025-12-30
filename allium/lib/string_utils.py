"""
File: string_utils.py

Phase 2 DRY Helper Functions - String Literals and Constants Consolidation
Provides centralized string formatting utilities to eliminate duplication across the codebase.

DEPRECATED: Use html_escape_utils.py for HTML escaping operations.
This module is maintained for backward compatibility.
"""

from typing import Optional

# Import from centralized HTML escaping utilities
from .html_escape_utils import (
    safe_html_escape,
    UNKNOWN_ESCAPED,
    UNKNOWN_LOWERCASE, 
    NONE_ESCAPED,
    NA_FALLBACK
)


def is_valid_aroi(aroi: Optional[str]) -> bool:
    """
    Check if AROI domain is valid (not None, empty, or 'none').
    
    This pattern was used 20+ times across the codebase as:
        `aroi_domain and aroi_domain != 'none'`
    
    Centralizing here for DRY compliance and consistency.
    
    Args:
        aroi: AROI domain string to validate
        
    Returns:
        bool: True if AROI is a valid non-empty string that isn't 'none'
        
    Example:
        >>> is_valid_aroi(None)
        False
        >>> is_valid_aroi('')
        False
        >>> is_valid_aroi('none')
        False
        >>> is_valid_aroi('example.com')
        True
    """
    return bool(aroi) and aroi != 'none'

def format_percentage(value, decimals=1, fallback=NA_FALLBACK):
    """
    Format a decimal value as a percentage with consistent decimal places.
    
    Args:
        value: Decimal value (e.g., 0.1234 for 12.34%)
        decimals: Number of decimal places (default: 1)
        fallback: Fallback string for None/invalid values (default: "N/A")
    
    Returns:
        str: Formatted percentage string (e.g., "12.3%")
    """
    if value is None:
        return fallback
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return fallback

def format_percentage_or_na(value, decimals=2):
    """
    Format a fraction as percentage or return "N/A" - specialized for relay data.
    
    Args:
        value: Decimal fraction value 
        decimals: Number of decimal places (default: 2 for relay probabilities)
    
    Returns:
        str: Formatted percentage or "N/A"
    """
    return format_percentage(value, decimals, NA_FALLBACK)

def format_percentage_from_fraction(value, decimals=1, fallback=NA_FALLBACK):
    """
    Format a fraction as percentage (multiply by 100) with consistent decimal places.
    
    Args:
        value: Fraction value (e.g., 0.1234 for 12.34%)
        decimals: Number of decimal places (default: 1)
        fallback: Fallback string for None/invalid values (default: "N/A")
    
    Returns:
        str: Formatted percentage string (e.g., "12.3%")
    """
    if value is None:
        return fallback
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return fallback