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


import re

def extract_contact_display_name(contact: Optional[str], aroi_domain: Optional[str] = None) -> str:
    """
    Extract the best unique display name from a contact string.
    
    Priority order for uniqueness:
    1. AROI domain (if provided and valid)
    2. Full email address (extracted from various formats)
    3. Person name (from "Name <email>" format)
    4. Leading URL domain
    5. Raw contact string (CSS will handle overflow with ellipsis)
    
    Key insight: Full email is the unique identifier, not just the domain.
    Using just domain (like gmail.com) would group 200+ different operators together.
    
    Args:
        contact: The raw contact string
        aroi_domain: Pre-extracted AROI domain (optional)
    
    Returns:
        str: Best display name for the contact
        
    Examples:
        >>> extract_contact_display_name("email:tor[]example.com url:example.com proof:uri-rsa ciissversion:2", "example.com")
        'example.com'
        >>> extract_contact_display_name("Brandon Kuschel <tor AT NOSPAM brandonkuschel dot com>")
        'tor@brandonkuschel.com'
        >>> extract_contact_display_name("nagubandi456@gmail.com")
        'nagubandi456@gmail.com'
        >>> extract_contact_display_name("relay // at // pommespanzer // dot // cc")
        'relay // at // pommespanzer // dot // cc'
    """
    # Priority 1: AROI domain (already validated/extracted)
    if is_valid_aroi(aroi_domain):
        return aroi_domain
    
    if not contact or contact.strip() == '':
        return 'none'
    
    contact = contact.strip()
    
    # Priority 2: Extract email from various formats
    email = _extract_email_from_contact(contact)
    if email:
        return email
    
    # Priority 3: Person name from "Name <...>" format
    name_match = re.match(r'^([A-Z][a-zA-Z\s\-]+)\s*<', contact)
    if name_match:
        name = name_match.group(1).strip()
        # Exclude generic/placeholder names
        if len(name) > 2 and name.lower() not in ['random person', 'dave null', 'abuse team']:
            return name
    
    # Priority 4: Leading URL domain
    if contact.startswith('http'):
        url_match = re.match(r'^https?://(?:www\.)?([^\s,/]+)', contact)
        if url_match:
            return url_match.group(1).lower()
    
    # Priority 5: Raw contact string (CSS ellipsis handles overflow)
    return contact


def _extract_email_from_contact(contact: str) -> Optional[str]:
    """
    Extract email address from contact string using multiple patterns.
    
    Handles:
    - CIISS format: email:user[]domain.com or email:user@domain.com
    - Standard format: user@domain.com
    - Obfuscated with []: user[]domain.com
    - Obfuscated with AT: user AT domain DOT com
    
    Args:
        contact: Contact string to extract email from
        
    Returns:
        str or None: Extracted email address or None if not found
    """
    # Pattern 1: CIISS-style email field (email:user[]domain or email:user@domain)
    ciiss_match = re.search(r'\bemail:([^\s,]+)', contact, re.I)
    if ciiss_match:
        email = ciiss_match.group(1)
        email = email.replace('[]', '@').replace('[@]', '@')
        if '@' in email and '.' in email.split('@')[-1]:
            return email
    
    # Pattern 2: mail: field variant
    mail_match = re.search(r'\bmail:([^\s,]+)', contact, re.I)
    if mail_match:
        email = mail_match.group(1)
        email = email.replace('[]', '@')
        if '@' in email and '.' in email.split('@')[-1]:
            return email
    
    # Pattern 3: Standard email format
    std_match = re.search(r'([\w\.\-+]+@[\w\.\-]+\.\w{2,})', contact)
    if std_match:
        return std_match.group(1)
    
    # Pattern 4: Obfuscated with [] brackets (user[]domain.com)
    bracket_match = re.search(r'([\w\.\-+]+)\s*\[\]\s*([\w\.\-]+\.\w{2,})', contact)
    if bracket_match:
        return f"{bracket_match.group(1)}@{bracket_match.group(2)}"
    
    # Pattern 5: AT NOSPAM style (user AT NOSPAM domain DOT com)
    nospam_match = re.search(
        r'([\w\.\-+]+)\s+AT\s+NOSPAM\s+([\w\.\-]+)\s+(?:DOT|dot|\.)\s*(\w{2,})',
        contact, re.I
    )
    if nospam_match:
        return f"{nospam_match.group(1)}@{nospam_match.group(2)}.{nospam_match.group(3)}"
    
    # Pattern 6: AT style without NOSPAM (user AT domain DOT com)
    at_match = re.search(
        r'([\w\.\-+]+)\s+(?:AT|at|\(at\)|\[at\])\s+([\w\.\-]+)\s+(?:DOT|dot|\.)\s*(\w{2,})',
        contact, re.I
    )
    if at_match:
        return f"{at_match.group(1)}@{at_match.group(2)}.{at_match.group(3)}"
    
    # Pattern 7: _at_ style (user_at_domain (dot) com)
    underscore_match = re.search(
        r'([\w\.\-]+)_at_([\w\.\-]+)\s*\(dot\)\s*(\w{2,})',
        contact, re.I
    )
    if underscore_match:
        return f"{underscore_match.group(1)}@{underscore_match.group(2)}.{underscore_match.group(3)}"
    
    return None