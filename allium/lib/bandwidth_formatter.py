"""
File: bandwidth_formatter.py

Unified Bandwidth Formatter - consolidates duplicate bandwidth formatting functions
from relays.py. This eliminates the DRY violations across the codebase.

Replaces:
- determine_unit() (global function)
- get_divisor_for_unit() (global function) 
- format_bandwidth_with_unit() (global function)
- determine_unit_filter() (Jinja2 filter function)
- format_bandwidth_filter() (Jinja2 filter function)
- _determine_unit() (Relays method)
- _get_divisor_for_unit() (Relays method)
- _format_bandwidth_with_unit() (Relays method)
"""


class BandwidthFormatter:
    """
    Unified bandwidth formatting utility that handles both bits and bytes units.
    
    This class consolidates all bandwidth formatting logic that was previously
    duplicated across multiple functions and methods in relays.py.
    """
    
    # Pre-computed divisor lookup table for maximum performance
    _DIVISORS = {
        # Bits (convert bytes to bits, then to unit)
        "Gbit/s": 125000000,   # 1000000000 / 8
        "Mbit/s": 125000,      # 1000000 / 8  
        "Kbit/s": 125,         # 1000 / 8
        # Bytes  
        "GB/s": 1000000000,
        "MB/s": 1000000,
        "KB/s": 1000
    }
    
    def __init__(self, use_bits=False):
        """
        Initialize bandwidth formatter.
        
        Args:
            use_bits (bool): If True, use bits/second units (Kbit/s, Mbit/s, Gbit/s).
                           If False, use bytes/second units (KB/s, MB/s, GB/s).
        """
        self.use_bits = use_bits
    
    def determine_unit(self, bandwidth_bytes):
        """
        Determine appropriate unit for the given bandwidth in bytes.
        
        Args:
            bandwidth_bytes (int): Bandwidth value in bytes per second
            
        Returns:
            str: Appropriate unit (e.g., "Mbit/s", "MB/s")
        """
        if self.use_bits:
            bits = bandwidth_bytes * 8
            if bits >= 1000000000:  # If greater than or equal to 1 Gbit/s
                return "Gbit/s"
            elif bits >= 1000000:  # If greater than or equal to 1 Mbit/s
                return "Mbit/s"
            else:
                return "Kbit/s"
        else:
            if bandwidth_bytes >= 1000000000:  # If greater than or equal to 1 GB/s
                return "GB/s"
            elif bandwidth_bytes >= 1000000:  # If greater than or equal to 1 MB/s
                return "MB/s"
            else:
                return "KB/s"
    
    def get_divisor_for_unit(self, unit):
        """
        Get divisor for converting bytes to the specified unit.
        
        Args:
            unit (str): Target unit (e.g., "Mbit/s", "GB/s")
            
        Returns:
            int: Divisor value
            
        Raises:
            ValueError: If unit is not recognized
        """
        if unit in self._DIVISORS:
            return self._DIVISORS[unit]
        raise ValueError(f"Unknown unit: {unit}")
    
    def format_bandwidth_with_unit(self, bandwidth_bytes, unit, decimal_places=2):
        """
        Format bandwidth value using the specified unit.
        
        Args:
            bandwidth_bytes (int): Bandwidth value in bytes per second
            unit (str): Target unit for formatting
            decimal_places (int): Number of decimal places to show
            
        Returns:
            str: Formatted bandwidth value (without unit suffix)
            
        Raises:
            ValueError: If unit is not recognized
        """
        divisor = self.get_divisor_for_unit(unit)
        value = bandwidth_bytes / divisor
        return f"{value:.{decimal_places}f}"
    
    def format_bandwidth(self, bandwidth_bytes, unit=None, decimal_places=2):
        """
        Format bandwidth with automatic or specified unit.
        
        Args:
            bandwidth_bytes (int): Bandwidth value in bytes per second
            unit (str, optional): Target unit. If None, determines automatically
            decimal_places (int): Number of decimal places to show
            
        Returns:
            str: Formatted bandwidth value (without unit suffix)
        """
        if unit is None:
            unit = self.determine_unit(bandwidth_bytes)
        
        return self.format_bandwidth_with_unit(bandwidth_bytes, unit, decimal_places)
    
    def format_bandwidth_with_suffix(self, bandwidth_bytes, unit=None, decimal_places=2):
        """
        Format bandwidth with unit suffix included.
        
        Args:
            bandwidth_bytes (int): Bandwidth value in bytes per second
            unit (str, optional): Target unit. If None, determines automatically
            decimal_places (int): Number of decimal places to show
            
        Returns:
            str: Formatted bandwidth value with unit suffix (e.g., "15.2 Mbit/s")
        """
        if unit is None:
            unit = self.determine_unit(bandwidth_bytes)
        
        value = self.format_bandwidth_with_unit(bandwidth_bytes, unit, decimal_places)
        return f"{value} {unit}"


# Convenience functions for backwards compatibility and Jinja2 filters
def determine_unit(bandwidth_bytes, use_bits=False):
    """Convenience function that creates a formatter and determines unit."""
    formatter = BandwidthFormatter(use_bits=use_bits)
    return formatter.determine_unit(bandwidth_bytes)


def get_divisor_for_unit(unit):
    """Convenience function that gets divisor for a unit."""
    # Use a dummy formatter since divisors are static
    formatter = BandwidthFormatter()
    return formatter.get_divisor_for_unit(unit)


def format_bandwidth_with_unit(bandwidth_bytes, unit, decimal_places=2):
    """Convenience function that formats bandwidth with specified unit."""
    # Use a dummy formatter since this doesn't depend on use_bits
    formatter = BandwidthFormatter()
    return formatter.format_bandwidth_with_unit(bandwidth_bytes, unit, decimal_places)


def determine_unit_filter(bandwidth_bytes, use_bits=False):
    """Jinja2 filter version of determine_unit."""
    return determine_unit(bandwidth_bytes, use_bits)


def format_bandwidth_filter(bandwidth_bytes, unit=None, use_bits=False, decimal_places=2):
    """Jinja2 filter for formatting bandwidth with optional unit specification."""
    formatter = BandwidthFormatter(use_bits=use_bits)
    return formatter.format_bandwidth(bandwidth_bytes, unit, decimal_places)


# =============================================================================
# CUMULATIVE DATA VOLUME FORMATTING (for total data transferred)
# =============================================================================

def format_data_volume(total_bytes, use_bits=False):
    """Format cumulative data volume in human-readable form.
    
    Unlike bandwidth formatting (bytes/sec rates), data *volumes* are
    universally expressed in bytes (TB, GB, PB).  The ``use_bits``
    parameter is accepted for API consistency with BandwidthFormatter
    but is intentionally ignored — "I transferred 3 TB" is standard;
    "I transferred 24 Tbit" is not.
    
    Args:
        total_bytes (float): Total bytes transferred
        use_bits (bool): Accepted for API compatibility but ignored.
                         Data volumes are always displayed in bytes.
    Returns:
        tuple: (formatted_value_str, unit_str) e.g. ('3.74', 'TB')
    """
    if total_bytes >= 1e15:
        return f"{total_bytes / 1e15:.2f}", "PB"
    elif total_bytes >= 1e12:
        return f"{total_bytes / 1e12:.2f}", "TB"
    elif total_bytes >= 1e9:
        return f"{total_bytes / 1e9:.2f}", "GB"
    elif total_bytes >= 1e6:
        return f"{total_bytes / 1e6:.2f}", "MB"
    else:
        return f"{total_bytes / 1e3:.2f}", "KB"


def format_data_volume_with_unit(total_bytes, use_bits=False):
    """Format cumulative data volume as a single string like '3.74 TB'.
    
    Returns 'N/A' for zero, negative, or falsy values.
    The ``use_bits`` parameter is accepted for API compatibility but
    ignored — data volumes are always displayed in bytes (TB, GB, PB).
    
    Args:
        total_bytes (float): Total bytes transferred
        use_bits (bool): Accepted for API compatibility but ignored.
    Returns:
        str: Formatted string e.g. '3.74 TB' or 'N/A'
    """
    if not total_bytes or total_bytes <= 0:
        return "N/A"
    value, unit = format_data_volume(total_bytes)
    return f"{value} {unit}"