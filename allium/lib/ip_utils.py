"""
File: ip_utils.py

IP address utility functions for validation, classification, and IPv6 support
detection used throughout the allium codebase.
"""

import ipaddress

from .aroileaders import _safe_parse_ip_address


def is_private_ip_address(ip_str):
    """
    Compute-efficient helper function to determine if an IP address or CIDR range
    represents a private/local IP address that should not be counted as a meaningful
    restriction for exit relays. Uses safe IP parsing for validation and follows DRY principles.
    
    Detects private IPv4 ranges:
    - 0.0.0.0/8 (IANA special use - "this network")
    - 10.0.0.0/8 (10.x.x.x)
    - 127.0.0.0/8 (localhost)
    - 169.254.0.0/16 (link-local)
    - 172.16.0.0/12 (172.16.x.x - 172.31.x.x)
    - 192.168.0.0/16 (192.168.x.x)
    
    And private IPv6 ranges:
    - ::1 (localhost)
    - fc00::/7 (unique local addresses - fc00:: to fdff::)
    - fe80::/10 (link-local)
    
    Args:
        ip_str (str): IP address string, can include CIDR notation (e.g., "192.168.1.0/24")
    
    Returns:
        bool: True if the IP address/range is private/local, False if public
    """
    if not ip_str or ip_str == '*':
        return False  # Wildcard is not private
    
    # Remove CIDR notation if present
    ip_clean = ip_str.split('/')[0].strip()
    
    # Use safe IP parsing for validation and version detection
    parsed_ip, ip_version = _safe_parse_ip_address(ip_clean)
    
    if not parsed_ip:
        return False  # Invalid IP address, assume public
    
    try:
        ip_obj = ipaddress.ip_address(parsed_ip)
        
        # Use Python's built-in private detection
        return ip_obj.is_private
        
    except Exception:
        return False  # If parsing fails, assume public


def determine_ipv6_support(or_addresses):
    """
    Helper function to determine IPv6 support status based on or_addresses.
    Uses safe IP parsing for validation and follows DRY principles.
    
    Args:
        or_addresses (list): List of address:port strings from onionoo
        
    Returns:
        str: 'ipv4_only', 'ipv6_only', 'both', or 'none'
    """
    if not or_addresses:
        return 'none'
        
    has_ipv4 = False
    has_ipv6 = False
    
    for address in or_addresses:
        # Use safe IP parsing for validation and IP version detection
        parsed_ip, ip_version = _safe_parse_ip_address(address)
        
        if parsed_ip:  # Valid IP address parsed
            if ip_version == 4:
                has_ipv4 = True
            elif ip_version == 6:
                has_ipv6 = True
    
    if has_ipv4 and has_ipv6:
        return 'both'
    elif has_ipv4:
        return 'ipv4_only'
    elif has_ipv6:
        return 'ipv6_only'
    else:
        return 'none'
