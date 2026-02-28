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
    def _smart_fmt(val):
        """Use 1 decimal for single-digit values (e.g. 1.3 TB), 0 for 10+.
        Handles the edge case where 9.95+ rounds up to 10.0 with .1f."""
        if round(val, 1) < 10:
            return f"{val:.1f}"
        return f"{val:.0f}"

    if total_bytes >= 1e15:
        return _smart_fmt(total_bytes / 1e15), "PB"
    elif total_bytes >= 1e12:
        return _smart_fmt(total_bytes / 1e12), "TB"
    elif total_bytes >= 1e9:
        return _smart_fmt(total_bytes / 1e9), "GB"
    elif total_bytes >= 1e6:
        return _smart_fmt(total_bytes / 1e6), "MB"
    else:
        return _smart_fmt(total_bytes / 1e3), "KB"


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


_BEST_PERIOD_ORDER = ('5_years', '1_year', '6_months', '1_month')

def pick_best_period(sums):
    """Return (total, period) for the longest period with non-zero data.

    Args:
        sums: dict mapping period keys to numeric totals
    Returns:
        tuple: (total_bytes, period_key) or (0, None) if all zero
    """
    for p in _BEST_PERIOD_ORDER:
        val = sums.get(p, 0)
        if val > 0:
            return val, p
    return 0, None


_PERIOD_LABELS = {
    '1_month': '1mo', '6_months': '6mo', '1_year': '1yr', '5_years': '5yr',
}

def compute_total_data_pct(total_bytes, period, network_totals_by_period):
    """Compute period-matched percentage of network total data.

    Args:
        total_bytes: Operator/group total bytes for `period`
        period: One of '1_month', '6_months', '1_year', '5_years'
        network_totals_by_period: dict from network_health['network_total_data_by_period']
    Returns:
        str: e.g. "2.20% of 6mo network data" or "" if negligible/no data
    """
    if not total_bytes or total_bytes <= 0 or not network_totals_by_period:
        return ""
    denom = network_totals_by_period.get(period, 0)
    if denom <= 0:
        return ""
    pct = total_bytes / denom * 100
    if pct < 0.01:
        return ""
    label = _PERIOD_LABELS.get(period, period)
    return f"{pct:.2f}% of {label} network data"
