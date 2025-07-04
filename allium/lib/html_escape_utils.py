#!/usr/bin/env python3
"""
HTML Escaping Utilities - consolidates all scattered HTML escaping patterns.

This module provides:
- Centralized HTML escaping with consistent fallback handling
- Field-specific escaping functions 
- Bulk escaping operations for template preprocessing
- Consistent fallback values across the codebase
"""

import html
from typing import Any, Dict, List, Optional, Union


class HTMLEscapeConstants:
    """Centralized HTML escaping constants for consistency."""
    
    UNKNOWN_ESCAPED = "Unknown"
    UNKNOWN_LOWERCASE = "unknown"
    NONE_ESCAPED = "none"
    NA_FALLBACK = "N/A"
    EMPTY_STRING = ""


class HTMLEscaper:
    """Centralized HTML escaping utility class."""
    
    def __init__(self):
        """Initialize with standard constants."""
        self.constants = HTMLEscapeConstants()
    
    def safe_escape(self, value: Any, fallback: str = "") -> str:
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
    
    def escape_with_unknown_fallback(self, value: Any) -> str:
        """Escape with 'Unknown' fallback for user-visible fields."""
        return self.safe_escape(value, self.constants.UNKNOWN_ESCAPED)
    
    def escape_with_none_fallback(self, value: Any) -> str:
        """Escape with 'none' fallback for technical fields."""
        return self.safe_escape(value, self.constants.NONE_ESCAPED)
    
    def escape_with_lowercase_unknown_fallback(self, value: Any) -> str:
        """Escape with 'unknown' fallback for lowercase contexts."""
        return self.safe_escape(value, self.constants.UNKNOWN_LOWERCASE)
    
    def escape_list(self, values: List[Any], fallback: str = "") -> List[str]:
        """
        Escape a list of values with consistent fallback handling.
        
        Args:
            values: List of values to escape
            fallback: Fallback for individual None/empty values
            
        Returns:
            List[str]: List of escaped strings
        """
        if not values:
            return []
        return [self.safe_escape(value, fallback) for value in values]
    
    def escape_with_truncation(self, value: Any, max_length: int, fallback: str = "") -> str:
        """
        Escape and truncate a value to specified length.
        
        Args:
            value: Value to escape and truncate
            max_length: Maximum length after truncation
            fallback: Fallback if value is None/empty
            
        Returns:
            str: Escaped and truncated string
        """
        if value is None or value == "":
            return fallback
        
        str_value = str(value)
        if len(str_value) > max_length:
            str_value = str_value[:max_length]
        
        return html.escape(str_value)


class RelayFieldEscaper:
    """Specialized escaper for relay data fields."""
    
    def __init__(self):
        """Initialize with base escaper."""
        self.escaper = HTMLEscaper()
        self.constants = HTMLEscapeConstants()
    
    def escape_contact_field(self, contact: Any) -> Dict[str, str]:
        """
        Escape contact field with consistent fallback handling.
        
        Returns:
            Dict with 'escaped' and 'raw' keys
        """
        if contact:
            return {
                'escaped': self.escaper.safe_escape(contact),
                'raw': str(contact)
            }
        else:
            return {
                'escaped': self.constants.EMPTY_STRING,
                'raw': self.constants.EMPTY_STRING
            }
    
    def escape_flags_field(self, flags: List[str]) -> Dict[str, List[str]]:
        """
        Escape flags field with both normal and lowercase versions.
        
        Returns:
            Dict with 'escaped', 'lower_escaped', and 'raw' keys
        """
        if flags:
            return {
                'escaped': self.escaper.escape_list(flags),
                'lower_escaped': self.escaper.escape_list([flag.lower() for flag in flags]),
                'raw': flags
            }
        else:
            return {
                'escaped': [],
                'lower_escaped': [],
                'raw': []
            }
    
    def escape_nickname_field(self, nickname: Any) -> Dict[str, str]:
        """
        Escape nickname field with truncation options.
        
        Returns:
            Dict with 'escaped', 'truncated', and 'raw' keys
        """
        if nickname:
            nickname_str = str(nickname)
            return {
                'escaped': self.escaper.safe_escape(nickname_str),
                'truncated': self.escaper.escape_with_truncation(nickname_str, 14),
                'raw': nickname_str
            }
        else:
            return {
                'escaped': self.constants.UNKNOWN_ESCAPED,
                'truncated': self.constants.UNKNOWN_ESCAPED,
                'raw': ""
            }
    
    def escape_platform_field(self, platform: Any) -> Dict[str, str]:
        """
        Escape platform field with truncation options.
        
        Returns:
            Dict with 'escaped', 'truncated', and 'raw' keys
        """
        if platform:
            platform_str = str(platform)
            return {
                'escaped': self.escaper.safe_escape(platform_str),
                'truncated': self.escaper.escape_with_truncation(platform_str, 10),
                'raw': platform_str
            }
        else:
            return {
                'escaped': self.constants.UNKNOWN_ESCAPED,
                'truncated': self.constants.UNKNOWN_ESCAPED,
                'raw': ""
            }
    
    def escape_as_name_field(self, as_name: Any) -> Dict[str, str]:
        """
        Escape AS name field with truncation options.
        
        Returns:
            Dict with 'escaped', 'truncated', and 'raw' keys
        """
        if as_name:
            as_name_str = str(as_name)
            return {
                'escaped': self.escaper.safe_escape(as_name_str),
                'truncated': self.escaper.escape_with_truncation(as_name_str, 20),
                'raw': as_name_str
            }
        else:
            return {
                'escaped': self.constants.UNKNOWN_ESCAPED,
                'truncated': self.constants.UNKNOWN_ESCAPED,
                'raw': ""
            }
    
    def escape_aroi_domain_field(self, aroi_domain: Any) -> Dict[str, str]:
        """
        Escape AROI domain field.
        
        Returns:
            Dict with 'escaped' and 'raw' keys
        """
        if aroi_domain and aroi_domain != "none":
            return {
                'escaped': self.escaper.safe_escape(aroi_domain),
                'raw': str(aroi_domain)
            }
        else:
            return {
                'escaped': self.constants.NONE_ESCAPED,
                'raw': "none"
            }
    
    def escape_date_field(self, date_field: Any) -> Dict[str, str]:
        """
        Escape date field with date extraction.
        
        Returns:
            Dict with 'escaped', 'date_escaped', and 'raw' keys
        """
        if date_field:
            date_str = str(date_field)
            date_only = date_str.split(' ', 1)[0]
            return {
                'escaped': self.escaper.safe_escape(date_str),
                'date_escaped': self.escaper.safe_escape(date_only),
                'raw': date_str
            }
        else:
            return {
                'escaped': self.constants.EMPTY_STRING,
                'date_escaped': self.constants.EMPTY_STRING,
                'raw': ""
            }


class BulkRelayEscaper:
    """Bulk escaping operations for template preprocessing."""
    
    def __init__(self):
        """Initialize with field escaper."""
        self.field_escaper = RelayFieldEscaper()
        self.escaper = HTMLEscaper()
    
    def escape_all_relay_fields(self, relay: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply comprehensive HTML escaping to a single relay object.
        
        Consolidates all the scattered escaping patterns from _preprocess_template_data.
        
        Args:
            relay: Single relay dictionary
            
        Returns:
            Dict: The relay with all escaped fields added
        """
        # Contact field escaping
        contact_data = self.field_escaper.escape_contact_field(relay.get("contact"))
        relay["contact_escaped"] = contact_data['escaped']
        
        # Flags field escaping  
        flags_data = self.field_escaper.escape_flags_field(relay.get("flags"))
        relay["flags_escaped"] = flags_data['escaped']
        relay["flags_lower_escaped"] = flags_data['lower_escaped']
        
        # Nickname field escaping
        nickname_data = self.field_escaper.escape_nickname_field(relay.get("nickname"))
        relay["nickname_escaped"] = nickname_data['escaped']
        relay["nickname_truncated"] = nickname_data['truncated']
        
        # Platform field escaping
        platform_data = self.field_escaper.escape_platform_field(relay.get("platform"))
        relay["platform_escaped"] = platform_data['escaped']
        relay["platform_truncated"] = platform_data['truncated']
        
        # AS name field escaping
        as_name_data = self.field_escaper.escape_as_name_field(relay.get("as_name"))
        relay["as_name_escaped"] = as_name_data['escaped']
        relay["as_name_truncated"] = as_name_data['truncated']
        
        # AROI domain field escaping
        aroi_data = self.field_escaper.escape_aroi_domain_field(relay.get("aroi_domain"))
        relay["aroi_domain_escaped"] = aroi_data['escaped']
        
        # Date field escaping
        first_seen_data = self.field_escaper.escape_date_field(relay.get("first_seen"))
        relay["first_seen_date"] = first_seen_data['date_escaped'].replace('&', '&amp;')  # Unescape for raw date
        relay["first_seen_date_escaped"] = first_seen_data['date_escaped']
        
        return relay
    
    def escape_all_relays(self, relays_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply bulk HTML escaping to all relays.
        
        Replaces the manual escaping patterns in _preprocess_template_data.
        
        Args:
            relays_list: List of relay dictionaries
            
        Returns:
            List[Dict]: List of relays with escaped fields added
        """
        return [self.escape_all_relay_fields(relay) for relay in relays_list]


class TemplateEscapingHelpers:
    """Helper functions for template-specific escaping patterns."""
    
    def __init__(self):
        """Initialize with base escaper."""
        self.escaper = HTMLEscaper()
    
    def escape_breadcrumb_data(self, breadcrumb_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Escape breadcrumb navigation data consistently.
        
        Consolidates breadcrumb escaping patterns from templates.
        
        Args:
            breadcrumb_data: Dictionary of breadcrumb data
            
        Returns:
            Dict[str, str]: Escaped breadcrumb data
        """
        escaped_data = {}
        
        # Standard breadcrumb fields
        standard_fields = [
            'as_number', 'country_name', 'platform_name', 'nickname',
            'contact_hash', 'family_hash', 'date', 'flag_name', 'aroi_domain'
        ]
        
        for field in standard_fields:
            if field in breadcrumb_data:
                escaped_data[field] = self.escaper.safe_escape(breadcrumb_data[field])
        
        # Special handling for hash truncation
        if 'contact_hash' in breadcrumb_data:
            escaped_data['contact_hash_short'] = self.escaper.safe_escape(
                str(breadcrumb_data['contact_hash'])[:8]
            )
        
        if 'family_hash' in breadcrumb_data:
            escaped_data['family_hash_short'] = self.escaper.safe_escape(
                str(breadcrumb_data['family_hash'])[:8]
            )
        
        return escaped_data
    
    def escape_or_addresses(self, or_addresses: List[str]) -> List[str]:
        """
        Escape OR addresses list for template usage.
        
        Addresses the OR address escaping patterns in relay-info.html.
        
        Args:
            or_addresses: List of OR addresses
            
        Returns:
            List[str]: List of escaped OR addresses
        """
        return self.escaper.escape_list(or_addresses)


# Convenience functions for backward compatibility and ease of use
def safe_html_escape(value: Any, fallback: str = "") -> str:
    """
    Safely escape HTML content with consistent fallback handling.
    
    Convenience function for quick escaping operations.
    """
    escaper = HTMLEscaper()
    return escaper.safe_escape(value, fallback)


def escape_relay_field(relay: Dict[str, Any], field_name: str, fallback: str = "") -> str:
    """
    Escape a specific field from a relay object.
    
    Convenience function for template usage.
    """
    escaper = HTMLEscaper()
    return escaper.safe_escape(relay.get(field_name), fallback)


def create_bulk_escaper() -> BulkRelayEscaper:
    """Create a new bulk relay escaper instance."""
    return BulkRelayEscaper()


def create_template_helpers() -> TemplateEscapingHelpers:
    """Create a new template escaping helpers instance."""
    return TemplateEscapingHelpers()


# Constants for external use
UNKNOWN_ESCAPED = HTMLEscapeConstants.UNKNOWN_ESCAPED
UNKNOWN_LOWERCASE = HTMLEscapeConstants.UNKNOWN_LOWERCASE
NONE_ESCAPED = HTMLEscapeConstants.NONE_ESCAPED
NA_FALLBACK = HTMLEscapeConstants.NA_FALLBACK