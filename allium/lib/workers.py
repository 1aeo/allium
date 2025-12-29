"""
File: workers.py

API worker functions for fetching data from multiple sources.
Extracted from the original monolithic Relays class for multi-API support.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import socket
import threading
from pathlib import Path
from .error_handlers import handle_file_io_errors, handle_http_errors, handle_json_errors

# Global constants
ABS_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(ABS_PATH), "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
STATE_FILE = os.path.join(DATA_DIR, "state.json")

# Ensure directories exist
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Global state lock for thread safety
_state_lock = threading.Lock()

# Worker status tracking
_worker_status = {}

# ============================================================================
# API CACHE CONFIGURATION
# ============================================================================
# These values control the timeout and caching behavior for each API.
# Adjust these values to tune the balance between responsiveness and data freshness.
#
# For each API:
#   - *_CACHE_MAX_AGE_HOURS: Age (in hours) after which cache is considered stale
#   - *_TIMEOUT_FRESH_CACHE: Timeout (in seconds) when cache is fresh (use cache on timeout)
#   - *_TIMEOUT_STALE_CACHE: Timeout (in seconds) when cache is stale or missing
#
# Example adjustments:
#   - For faster responses with older data: increase *_CACHE_MAX_AGE_HOURS
#   - For more patient fetching: increase *_TIMEOUT_STALE_CACHE
#   - For quicker timeouts: decrease *_TIMEOUT_FRESH_CACHE
# ============================================================================

# DETAILS API - Critical for operation, has most relay data
# Details API typically responds quickly but can be slow during high load
DETAILS_CACHE_MAX_AGE_HOURS = 6       # Cache older than this is considered stale
DETAILS_TIMEOUT_FRESH_CACHE = 90      # 90 seconds for fresh cache
DETAILS_TIMEOUT_STALE_CACHE = 300     # 5 minutes for stale/missing cache

# UPTIME API - Often slow, especially around 30 minutes past the hour
# Uptime API often can take up to 10 minutes around 30 minutes past the hour
UPTIME_CACHE_MAX_AGE_HOURS = 12       # Cache older than this is considered stale
UPTIME_TIMEOUT_FRESH_CACHE = 30       # 30 seconds for fresh cache (shorter due to frequent slowness)
UPTIME_TIMEOUT_STALE_CACHE = 1200     # 20 minutes for stale/missing cache

# BANDWIDTH API - Large data, can be slow
BANDWIDTH_CACHE_MAX_AGE_HOURS = 12    # Cache older than this is considered stale
BANDWIDTH_TIMEOUT_FRESH_CACHE = 90    # 90 seconds for fresh cache
BANDWIDTH_TIMEOUT_STALE_CACHE = 600   # 10 minutes for stale/missing cache

# AROI VALIDATION API - External API, may be less reliable
AROI_CACHE_MAX_AGE_HOURS = 1          # Cache older than this is considered stale (1 hour)
AROI_TIMEOUT_FRESH_CACHE = 90         # 90 seconds for fresh cache
AROI_TIMEOUT_STALE_CACHE = 120        # 2 minutes for stale/missing cache
# ============================================================================


# ============================================================================
# API CONFIGURATION DATACLASS
# ============================================================================
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable

@dataclass
class APIConfig:
    """Configuration for an API worker with cache and timeout settings."""
    api_name: str                    # Internal name for caching (e.g., 'onionoo_details')
    display_name: str                # Human-readable name for logging
    cache_max_age_hours: float       # Hours after which cache is considered stale
    timeout_fresh_cache: int         # Timeout (seconds) when cache is fresh
    timeout_stale_cache: int         # Timeout (seconds) when cache is stale/missing
    use_conditional_requests: bool = True   # Whether to use If-Modified-Since header
    custom_headers: Optional[Dict[str, str]] = None  # Additional request headers
    count_field: str = 'relays'      # Field name to count items in response


# Pre-configured API settings
DETAILS_CONFIG = APIConfig(
    api_name='onionoo_details',
    display_name='onionoo details',
    cache_max_age_hours=DETAILS_CACHE_MAX_AGE_HOURS,
    timeout_fresh_cache=DETAILS_TIMEOUT_FRESH_CACHE,
    timeout_stale_cache=DETAILS_TIMEOUT_STALE_CACHE,
)

UPTIME_CONFIG = APIConfig(
    api_name='onionoo_uptime',
    display_name='onionoo uptime',
    cache_max_age_hours=UPTIME_CACHE_MAX_AGE_HOURS,
    timeout_fresh_cache=UPTIME_TIMEOUT_FRESH_CACHE,
    timeout_stale_cache=UPTIME_TIMEOUT_STALE_CACHE,
)

BANDWIDTH_CONFIG = APIConfig(
    api_name='onionoo_bandwidth',
    display_name='onionoo historical bandwidth',
    cache_max_age_hours=BANDWIDTH_CACHE_MAX_AGE_HOURS,
    timeout_fresh_cache=BANDWIDTH_TIMEOUT_FRESH_CACHE,
    timeout_stale_cache=BANDWIDTH_TIMEOUT_STALE_CACHE,
)

AROI_CONFIG = APIConfig(
    api_name='aroi_validation',
    display_name='AROI validation',
    cache_max_age_hours=AROI_CACHE_MAX_AGE_HOURS,
    timeout_fresh_cache=AROI_TIMEOUT_FRESH_CACHE,
    timeout_stale_cache=AROI_TIMEOUT_STALE_CACHE,
    use_conditional_requests=False,
    custom_headers={'User-Agent': 'Allium/1.0'},
    count_field='results',
)
# ============================================================================


# Use centralized file I/O utilities
from .file_io_utils import create_cache_manager, create_timestamp_manager, create_state_manager

# Initialize file managers
_cache_manager = create_cache_manager(CACHE_DIR)
_timestamp_manager = create_timestamp_manager(CACHE_DIR)
_state_manager = create_state_manager(STATE_FILE)

def _save_cache(api_name, data):
    """
    Save API data to cache file using centralized cache manager.
    
    Args:
        api_name: Name of the API (e.g., 'onionoo_details')
        data: Data to cache (will be JSON serialized)
    """
    return _cache_manager.save_cache(api_name, data)


def _load_cache(api_name):
    """
    Load API data from cache file using centralized cache manager.
    
    Args:
        api_name: Name of the API (e.g., 'onionoo_details')
        
    Returns:
        Cached data or None if not available
    """
    return _cache_manager.load_cache(api_name)


def _mark_ready(api_name):
    """
    Mark API as successfully completed
    
    Args:
        api_name: Name of the API
    """
    with _state_lock:
        _worker_status[api_name] = {
            "status": "ready",
            "timestamp": time.time(),
            "error": None
        }
        _save_state()


def _mark_stale(api_name, error_msg):
    """
    Mark API as failed/stale
    
    Args:
        api_name: Name of the API
        error_msg: Error message
    """
    with _state_lock:
        _worker_status[api_name] = {
            "status": "stale",
            "timestamp": time.time(),
            "error": str(error_msg)
        }
        _save_state()


@handle_file_io_errors("save state")
def _save_state():
    """Save worker state to file (called with lock held)"""
    state_data = {
        "workers": _worker_status,
        "last_updated": time.time()
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state_data, f, indent=2)


@handle_file_io_errors("load state")
@handle_json_errors("parse state JSON", default_return={})
def _load_state():
    """Load worker state from file"""
    global _worker_status
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state_data = json.load(f)
            _worker_status = state_data.get("workers", {})
    else:
        _worker_status = {}


def get_worker_status(api_name):
    """
    Get status of a specific worker
    
    Args:
        api_name: Name of the API
        
    Returns:
        dict: Status information or None if not found
    """
    with _state_lock:
        return _worker_status.get(api_name, None)


def get_all_worker_status():
    """
    Get status of all workers
    
    Returns:
        dict: All worker status information
    """
    with _state_lock:
        return _worker_status.copy()


@handle_file_io_errors("save timestamp", context="")
def _write_timestamp(api_name, timestamp_str):
    """
    Store encoded timestamp for conditional requests using centralized timestamp manager.
    
    Args:
        api_name: Name of the API
        timestamp_str: Formatted timestamp string
    """
    return _timestamp_manager.write_timestamp(api_name, timestamp_str)


def _read_timestamp(api_name):
    """
    Read stored timestamp for conditional requests using centralized timestamp manager.
    
    Args:
        api_name: Name of the API
        
    Returns:
        str: Timestamp string or None if not available
    """
    return _timestamp_manager.read_timestamp(api_name)


# ============================================================================
# GENERIC API FETCH WITH CACHE FALLBACK
# ============================================================================

def _fetch_with_cache_fallback(
    url: str,
    config: APIConfig,
    progress_logger: Optional[Callable] = None,
    cache_hours_override: Optional[float] = None,
    return_fresh_cache: bool = False,
    validator: Optional[Callable[[dict], bool]] = None,
) -> Optional[dict]:
    """
    Generic function to fetch API data with smart caching and timeout fallback.
    
    This function implements the common pattern used by all API workers:
    1. Check cache age and validate cache can be loaded
    2. Determine timeout based on cache freshness
    3. Make HTTP request with appropriate timeout
    4. Fall back to cached data on timeout
    5. Save new data to cache on success
    
    Args:
        url: URL to fetch data from
        config: APIConfig with timeout and cache settings
        progress_logger: Optional function for progress messages
        cache_hours_override: Override config's cache_max_age_hours (e.g., for bandwidth API)
        return_fresh_cache: If True, return fresh cache immediately without fetching
        validator: Optional function to validate response data structure
        
    Returns:
        dict: Parsed JSON response or cached data, None if unavailable
    """
    api_name = config.api_name
    display_name = config.display_name
    cache_max_age_hours = cache_hours_override or config.cache_max_age_hours
    cache_max_age_seconds = cache_max_age_hours * 3600
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
    
    # Check cache age AND validate cache can be loaded
    cache_age = _cache_manager.get_cache_age(api_name)
    
    # Pre-load cache to verify it's valid (will be reused on timeout fallback)
    cached_data = None
    if cache_age is not None:
        cached_data = _load_cache(api_name)
        if cached_data is None:
            cache_age = None
            log_progress("cache file exists but is invalid, treating as no cache...")
    
    # If cache is fresh and valid, optionally return immediately
    if return_fresh_cache and cache_age is not None and cache_age < cache_max_age_seconds and cached_data:
        cache_age_display = cache_age / 3600 if cache_age >= 3600 else cache_age / 60
        cache_unit = "hours" if cache_age >= 3600 else "minutes"
        log_progress(f"using cached {display_name} data (less than {cache_max_age_hours} hour(s) old)")
        _mark_ready(api_name)
        item_count = len(cached_data.get(config.count_field, []))
        log_progress(f"loaded {item_count} items from {display_name} cache")
        return cached_data
    
    # Determine timeout based on cache state
    if cache_age is None:
        timeout_seconds = config.timeout_stale_cache
        timeout_display = timeout_seconds / 60
        log_progress(f"no valid cache exists, using {timeout_display:.0f} minute timeout for initial fetch...")
    elif cache_age >= cache_max_age_seconds:
        cache_hours_actual = cache_age / 3600
        timeout_seconds = config.timeout_stale_cache
        timeout_display = timeout_seconds / 60
        log_progress(f"cache is {cache_hours_actual:.1f} hours old (>={cache_max_age_hours}h), using {timeout_display:.0f} minute timeout to refresh...")
    else:
        cache_minutes = cache_age / 60
        timeout_seconds = config.timeout_fresh_cache
        log_progress(f"cache is {cache_minutes:.1f} minutes old (<{cache_max_age_hours}h), using {timeout_seconds} second timeout...")
    
    # Build request with optional conditional headers
    headers = dict(config.custom_headers) if config.custom_headers else {}
    if config.use_conditional_requests:
        prev_timestamp = _read_timestamp(api_name)
        if prev_timestamp:
            headers["If-Modified-Since"] = prev_timestamp
    
    if headers:
        conn = urllib.request.Request(url, headers=headers)
    else:
        conn = urllib.request.Request(url)
    
    # Try to fetch with timeout, fallback to cache on timeout
    try:
        api_response = urllib.request.urlopen(conn, timeout=timeout_seconds).read()
    except (socket.timeout, TimeoutError, urllib.error.URLError) as e:
        is_timeout = (
            isinstance(e, (socket.timeout, TimeoutError)) or 
            (isinstance(e, urllib.error.URLError) and isinstance(e.reason, (socket.timeout, TimeoutError)))
        )
        
        if is_timeout:
            log_progress(f"request timed out after {timeout_seconds} seconds...")
            if cached_data:
                log_progress(f"using cached {display_name} data due to timeout")
                _mark_ready(api_name)
                return cached_data
            else:
                log_progress("no cached data available after timeout")
                _mark_stale(api_name, f"Timeout after {timeout_seconds}s with no cache")
                return None
        else:
            raise
    
    # Parse JSON response
    log_progress("parsing JSON response...")
    data = json.loads(api_response.decode("utf-8"))
    
    # Validate response if validator provided
    if validator and not validator(data):
        log_progress(f"warning: invalid {display_name} data structure")
        if cached_data:
            log_progress("using cached data due to invalid response structure")
            _mark_ready(api_name)
            return cached_data
        return None
    
    # Cache the data
    log_progress(f"caching {display_name} data...")
    _save_cache(api_name, data)
    
    # Write timestamp for future conditional requests
    if config.use_conditional_requests:
        timestamp_str = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time()))
        _write_timestamp(api_name, timestamp_str)
    
    # Mark as ready
    _mark_ready(api_name)
    
    # Log success
    item_count = len(data.get(config.count_field, []))
    log_progress(f"successfully fetched {item_count} items from {display_name} API")
    
    return data

# ============================================================================


@handle_http_errors("onionoo details", _load_cache, _save_cache, _mark_ready, _mark_stale, 
                   allow_exit_on_304=True, critical=True)
def fetch_onionoo_details(onionoo_url="https://onionoo.torproject.org/details", progress_logger=None):
    """
    Fetch onionoo details data with smart caching and timeout fallback.
    
    Uses the generic _fetch_with_cache_fallback helper with DETAILS_CONFIG settings.
    
    Args:
        onionoo_url: URL to fetch data from
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response from onionoo API
    """
    # Create a wrapper logger that prints if no logger provided (for backwards compatibility)
    def log_wrapper(message):
        if progress_logger:
            progress_logger(message)
        else:
            print(message)
    
    return _fetch_with_cache_fallback(
        url=onionoo_url,
        config=DETAILS_CONFIG,
        progress_logger=log_wrapper,
    )


@handle_http_errors("onionoo uptime", _load_cache, _save_cache, _mark_ready, _mark_stale, 
                   allow_exit_on_304=False, critical=False)
def fetch_onionoo_uptime(onionoo_url="https://onionoo.torproject.org/uptime", progress_logger=None):
    """
    Fetch onionoo uptime data with smart caching and timeout fallback.
    
    Uses the generic _fetch_with_cache_fallback helper with UPTIME_CONFIG settings.
    
    Args:
        onionoo_url: URL to fetch uptime data from
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response from onionoo uptime API
    """
    return _fetch_with_cache_fallback(
        url=onionoo_url,
        config=UPTIME_CONFIG,
        progress_logger=progress_logger,
    )


@handle_http_errors("onionoo historical bandwidth", _load_cache, _save_cache, _mark_ready, _mark_stale, 
                   allow_exit_on_304=False, critical=False)
def fetch_onionoo_bandwidth(onionoo_url="https://onionoo.torproject.org/bandwidth", cache_hours=12, progress_logger=None):
    """
    Fetch onionoo historical bandwidth data with smart caching and timeout fallback.
    
    Uses the generic _fetch_with_cache_fallback helper with BANDWIDTH_CONFIG settings.
    Returns fresh cache immediately if available (no fetch needed for fresh data).
    
    Args:
        onionoo_url: URL to fetch historical bandwidth data from
        cache_hours: Hours to cache historical bandwidth data before refreshing (default: 12)
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response from onionoo historical bandwidth API or cached data
    """
    return _fetch_with_cache_fallback(
        url=onionoo_url,
        config=BANDWIDTH_CONFIG,
        progress_logger=progress_logger,
        cache_hours_override=cache_hours,
        return_fresh_cache=True,  # Return fresh cache immediately without fetching
    )


def _validate_aroi_response(data: dict) -> bool:
    """Validator for AROI API response structure."""
    required_keys = ['metadata', 'statistics', 'results']
    return all(key in data for key in required_keys)


@handle_http_errors("AROI validation", _load_cache, _save_cache, _mark_ready, _mark_stale,
                   allow_exit_on_304=False, critical=False)
def fetch_aroi_validation(aroi_url="https://aroivalidator.1aeo.com/latest.json", progress_logger=None):
    """
    Fetch AROI validation data with smart caching and timeout fallback.
    
    Uses the generic _fetch_with_cache_fallback helper with AROI_CONFIG settings.
    Returns fresh cache immediately if available (no fetch needed for fresh data).
    Validates response structure and falls back to cache if invalid.
    
    Args:
        aroi_url: URL to fetch AROI validation data from
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response with AROI validation data
    """
    # Create a wrapper logger that prints if no logger provided (for backwards compatibility)
    def log_wrapper(message):
        if progress_logger:
            progress_logger(message)
        else:
            print(message)
    
    return _fetch_with_cache_fallback(
        url=aroi_url,
        config=AROI_CONFIG,
        progress_logger=log_wrapper,
        return_fresh_cache=True,  # Return fresh cache immediately without fetching
        validator=_validate_aroi_response,
    )


def fetch_collector_data(progress_logger=None):
    """
    Fetch CollecTor data (placeholder for future implementation)
    
    Args:
        progress_logger: Optional function to call for progress updates
    
    Returns:
        dict: Processed CollecTor data
    """
    api_name = "collector"
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
        else:
            print(message)
    
    try:
        log_progress(f"Fetching {api_name} (placeholder implementation)")
        
        # Placeholder implementation - will be completed in Phase 3
        empty_data = {"authorities": [], "version": "placeholder"}
        _save_cache(api_name, empty_data)
        _mark_ready(api_name)
        
        return empty_data
        
    except Exception as e:
        error_msg = f"Failed to fetch collector data: {str(e)}"
        log_progress(f"Error: {error_msg}")
        _mark_stale(api_name, error_msg)
        return None


def fetch_consensus_health(progress_logger=None):
    """
    Fetch consensus health data (placeholder for future implementation)
    
    Args:
        progress_logger: Optional function to call for progress updates
    
    Returns:
        dict: Consensus health data
    """
    api_name = "consensus_health"
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
        else:
            print(message)
    
    try:
        log_progress(f"Fetching {api_name} (placeholder implementation)")
        
        # Placeholder implementation - will be completed in Phase 3
        empty_data = {"health_status": {}, "version": "placeholder"}
        _save_cache(api_name, empty_data)
        _mark_ready(api_name)
        
        return empty_data
        
    except Exception as e:
        error_msg = f"Failed to fetch consensus health: {str(e)}"
        log_progress(f"Error: {error_msg}")
        _mark_stale(api_name, error_msg)
        return None


# Initialize state on module import
_load_state() 