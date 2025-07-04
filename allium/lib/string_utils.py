"""
File: string_utils.py

Phase 2 DRY Helper Functions - String Literals and Constants Consolidation
Provides centralized string formatting utilities to eliminate duplication across the codebase.
"""

import html

# String Constants - Centralized for consistency
UNKNOWN_ESCAPED = "Unknown"
UNKNOWN_LOWERCASE = "unknown"
NONE_ESCAPED = "none"
NA_FALLBACK = "N/A"

def safe_html_escape(value, fallback=""):
    """
    Safely escape HTML content with consistent fallback handling.
    
    Args:
        value: The value to escape (can be None, str, or other types)
        fallback: Fallback value if input is None/empty (default: "")
    
    Returns:
        str: HTML-escaped string or fallback
    """
    if value is None or value == "":
        return fallback
    return html.escape(str(value))

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