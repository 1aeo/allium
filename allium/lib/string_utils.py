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

# =============================================================================
# PRECOMPILED REGEX PATTERNS (computed once at module load for performance)
# =============================================================================

# Email extraction patterns - ordered by specificity (most specific first)
_RE_EMAIL_CIISS = re.compile(r'\bemail:\s*([^\s,]+)', re.I)
_RE_EMAIL_MAIL = re.compile(r'\bmail:([^\s,]+)', re.I)
_RE_EMAIL_STANDARD = re.compile(r'([\w\.\-+]+@[\w\.\-]+\.\w{2,})')
_RE_EMAIL_BRACKETS = re.compile(r'([\w\.\-+]+)\s*\[\]\s*([\w\.\-]+\.\w{2,})')
# CIISS with [dot] for TLD: email:user[]domain[dot]tld
_RE_EMAIL_CIISS_DOT = re.compile(r'\bemail:\s*([\w\.\-+]+)\[\]([\w\.\-]+)\[dot\](\w{2,})', re.I)
_RE_EMAIL_AT_NOSPAM = re.compile(
    r'([\w\.\-+]+)\s+AT\s+NOSPAM\s+([\w\.\-]+)\s+(?:DOT|dot|\.)\s*(\w{2,})', re.I)
# Comprehensive AT/DOT style with various bracket formats
_RE_EMAIL_AT_STYLE = re.compile(
    r'([\w\.\-+]+)\s*(?:<AT>|<at>|\{AT\}|\{at\}|\(AT\)|\(at\)|\[AT\]|\[at\]|_at_|__at__|AT|at)\s*([\w\.\-]+)\s*(?:<DOT>|<dot>|\{DOT\}|\{dot\}|\(DOT\)|\(dot\)|\[DOT\]|\[dot\]|_dot_|__dot__|DOT|dot|\.)\s*(\w{2,})', re.I)
_RE_EMAIL_UNDERSCORE = re.compile(r'([\w\.\-]+)_at_([\w\.\-]+)\s*\(dot\)\s*(\w{2,})', re.I)
# Pattern for "user // at // domain // dot // tld" style
_RE_EMAIL_SLASH_STYLE = re.compile(
    r'([\w\.\-+]+)\s*//\s*at\s*//\s*([\w\.\-]+)\s*//\s*dot\s*//\s*(\w{2,})', re.I)
# Concatenated style: userATdomainDOTcom (no spaces/separators)
_RE_EMAIL_CONCAT = re.compile(r'([\w\.\-+]+)AT([\w\.\-]+)DOT(\w{2,})(?:\s|$)', re.I)
# {AT} or (at) with standard domain (domain.tld not obfuscated)
_RE_EMAIL_AT_STANDARD_DOMAIN = re.compile(
    r'([\w\.\-+]+)\s*(?:\{AT\}|\{at\}|\(at\)|\(AT\)|\[at\]|\[AT\])\s*([\w\.\-]+\.\w{2,})', re.I)
# Angle bracket wrapped: <user AT domain DOT tld> or <user _at_ domain _dot_ tld>
_RE_EMAIL_ANGLE_WRAPPED = re.compile(
    r'<\s*([\w\.\-+]+)\s*(?:AT|_at_|\[at\])\s*([\w\.\-]+)\s*(?:DOT|_dot_|\[dot\])\s*(\w{2,})\s*>', re.I)

# Person name pattern - matches "Name <...>" at start
_RE_PERSON_NAME = re.compile(r'^([A-Z][a-zA-Z\s\-]+)\s*<')

# URL patterns - leading URL or URL in angle brackets
_RE_LEADING_URL = re.compile(r'^https?://(?:www\.)?([^\s,/]+)')
_RE_ANGLE_BRACKET_URL = re.compile(r'<\s*https?://(?:www\.)?([^\s,/>]+)')
# Onion URL pattern - extract .onion domain from url: field or standalone
_RE_ONION_URL = re.compile(r'(?:url:)?https?://([a-z2-7]{56}\.onion)', re.I)

# Generic placeholder names to exclude
_PLACEHOLDER_NAMES = frozenset(['random person', 'dave null', 'abuse team'])


def extract_contact_display_name(contact: Optional[str], aroi_domain: Optional[str] = None) -> str:
    """
    Extract display name from contact string, combining available identifiers.
    
    For AROI contacts: Returns the AROI domain only.
    For non-AROI contacts: Combines available identifiers (name, email, url).
    
    Display format for non-AROI:
    - Name + Email: "Name (email)"
    - Email only: "email"
    - Name + URL: "Name (url)"
    - Name only: "Name"
    - URL only: "url"
    - None: raw contact string (CSS handles overflow)
    
    Args:
        contact: The raw contact string
        aroi_domain: Pre-extracted AROI domain (optional)
    
    Returns:
        str: Display name for the contact
        
    Examples:
        >>> extract_contact_display_name("...", "example.com")
        'example.com'
        >>> extract_contact_display_name("Brandon Kuschel <tor AT NOSPAM brandonkuschel dot com>")
        'Brandon Kuschel (tor@brandonkuschel.com)'
        >>> extract_contact_display_name("relay // at // pommespanzer // dot // cc")
        'relay@pommespanzer.cc'
    """
    # Priority 1: AROI domain takes precedence (already validated/extracted)
    if is_valid_aroi(aroi_domain):
        return aroi_domain
    
    if not contact or not contact.strip():
        return 'none'
    
    contact = contact.strip()
    
    # Extract all available identifiers (single pass through patterns)
    email = _extract_email_from_contact(contact)
    name = _extract_person_name(contact)
    url = _extract_leading_url(contact)
    
    # Combine available identifiers into display string
    return _format_display_name(email, name, url, contact)


def _format_display_name(email: Optional[str], name: Optional[str], 
                         url: Optional[str], raw_contact: str) -> str:
    """
    Combine available identifiers into a display string.
    
    Priority: email is most unique, name adds context, url is fallback.
    """
    # Name + Email: show both for maximum context
    if name and email:
        return f"{name} ({email})"
    
    # Email only: unique identifier
    if email:
        return email
    
    # Name + URL: name with url as context
    if name and url:
        return f"{name} ({url})"
    
    # Name only
    if name:
        return name
    
    # URL only
    if url:
        return url
    
    # Fallback: raw contact (CSS ellipsis handles overflow)
    return raw_contact


def _extract_person_name(contact: str) -> Optional[str]:
    """
    Extract person name from "Name <...>" format at start of contact.
    
    Returns None for placeholder/generic names.
    """
    match = _RE_PERSON_NAME.match(contact)
    if match:
        name = match.group(1).strip()
        # Exclude short names and known placeholders
        if len(name) > 2 and name.lower() not in _PLACEHOLDER_NAMES:
            return name
    return None


def _extract_leading_url(contact: str) -> Optional[str]:
    """
    Extract domain from URL at start of contact or in angle brackets.
    
    Handles:
    - Leading URL: "https://example.com/..."
    - Angle bracket URL: "Name <https://example.com/>"
    - Onion URL: "url:http://xyz...onion" or standalone
    """
    # Fast path: check for 'http' anywhere (covers both patterns)
    if 'http' not in contact:
        return None
    
    # Try onion URL first (higher priority for Tor network)
    match = _RE_ONION_URL.search(contact)
    if match:
        return match.group(1).lower()
    
    # Try leading URL first
    if contact.startswith('http'):
        match = _RE_LEADING_URL.match(contact)
        if match:
            return match.group(1).lower()
    
    # Try URL in angle brackets (for "Name <URL>" pattern)
    match = _RE_ANGLE_BRACKET_URL.search(contact)
    return match.group(1).lower() if match else None


def _extract_email_from_contact(contact: str) -> Optional[str]:
    """
    Extract email address from contact string using multiple patterns.
    
    Handles various obfuscation formats:
    - CIISS: email:user[]domain.com, email:user[]domain[dot]tld
    - Standard: user@domain.com
    - Brackets: user[]domain.com
    - AT style: user AT domain DOT com, user <AT> domain <DOT> com
    - Slash style: user // at // domain // dot // com
    - Concatenated: userATdomainDOTcom
    - Various bracket styles: {at}, (at), [at], _at_, __at__
    
    Uses precompiled patterns for performance.
    """
    # Pattern 1a: CIISS with [dot] for TLD (email:user[]domain[dot]tld)
    match = _RE_EMAIL_CIISS_DOT.search(contact)
    if match:
        return f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
    
    # Pattern 1b: CIISS-style email field (most common in Tor contacts)
    match = _RE_EMAIL_CIISS.search(contact)
    if match:
        email = match.group(1).replace('[]', '@').replace('[@]', '@')
        if _is_valid_email(email):
            return email
    
    # Pattern 2: mail: field variant
    match = _RE_EMAIL_MAIL.search(contact)
    if match:
        email = match.group(1).replace('[]', '@')
        if _is_valid_email(email):
            return email
    
    # Pattern 3: Standard email format (user@domain.tld)
    match = _RE_EMAIL_STANDARD.search(contact)
    if match:
        return match.group(1)
    
    # Pattern 4: Obfuscated with [] brackets (user[]domain.com)
    match = _RE_EMAIL_BRACKETS.search(contact)
    if match:
        return f"{match.group(1)}@{match.group(2)}"
    
    # Pattern 5: Angle bracket wrapped (<user AT domain DOT tld>)
    match = _RE_EMAIL_ANGLE_WRAPPED.search(contact)
    if match:
        return f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
    
    # Pattern 6: Slash style (user // at // domain // dot // tld)
    match = _RE_EMAIL_SLASH_STYLE.search(contact)
    if match:
        return f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
    
    # Pattern 7: AT NOSPAM style (user AT NOSPAM domain DOT com)
    match = _RE_EMAIL_AT_NOSPAM.search(contact)
    if match:
        return f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
    
    # Pattern 8: Concatenated style (userATdomainDOTcom)
    match = _RE_EMAIL_CONCAT.search(contact)
    if match:
        return f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
    
    # Pattern 9: {AT} or (at) with standard domain (user {AT} domain.tld)
    match = _RE_EMAIL_AT_STANDARD_DOMAIN.search(contact)
    if match:
        return f"{match.group(1)}@{match.group(2)}"
    
    # Pattern 10: AT style with various separators (user AT domain DOT com)
    match = _RE_EMAIL_AT_STYLE.search(contact)
    if match:
        return f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
    
    # Pattern 11: _at_ style (user_at_domain (dot) com)
    match = _RE_EMAIL_UNDERSCORE.search(contact)
    if match:
        return f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
    
    return None


def _is_valid_email(email: str) -> bool:
    """Check if string looks like a valid email (has @ and domain with dot)."""
    return '@' in email and '.' in email.split('@')[-1]