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
# UPTIME API CACHE CONFIGURATION
# ============================================================================
# These values control the timeout and caching behavior for the uptime API.
# Adjust these values to tune the balance between responsiveness and data freshness.
# Uptime API often can take up to 10 minutes around 30 minutes past the hour in Nov and Dec 2025
#
# UPTIME_CACHE_MAX_AGE_HOURS: Age (in hours) after which cache is considered stale
# UPTIME_TIMEOUT_FRESH_CACHE: Timeout (in seconds) when cache is fresh
# UPTIME_TIMEOUT_STALE_CACHE: Timeout (in seconds) when cache is stale or missing
#
# Example adjustments:
#   - For faster responses with older data: increase UPTIME_CACHE_MAX_AGE_HOURS
#   - For more patient fetching: increase UPTIME_TIMEOUT_STALE_CACHE
#   - For quicker timeouts: decrease UPTIME_TIMEOUT_FRESH_CACHE
# ============================================================================
UPTIME_CACHE_MAX_AGE_HOURS = 12      # Cache older than this is considered stale
UPTIME_TIMEOUT_FRESH_CACHE = 30      # 30 seconds for fresh cache
UPTIME_TIMEOUT_STALE_CACHE = 1200    # 20 minutes for stale/missing cache
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


@handle_http_errors("onionoo details", _load_cache, _save_cache, _mark_ready, _mark_stale, 
                   allow_exit_on_304=True, critical=True)
def fetch_onionoo_details(onionoo_url="https://onionoo.torproject.org/details", progress_logger=None):
    """
    Fetch onionoo details data (extracted from original Relays._fetch_onionoo_details)
    
    Args:
        onionoo_url: URL to fetch data from
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response from onionoo API
    """
    api_name = "onionoo_details"
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
        else:
            print(message)
    
    # Check for conditional request timestamp
    prev_timestamp = _read_timestamp(api_name)
    
    if prev_timestamp:
        headers = {"If-Modified-Since": prev_timestamp}
        conn = urllib.request.Request(onionoo_url, headers=headers)
    else:
        conn = urllib.request.Request(onionoo_url)

    # Add timeout to prevent hanging in CI environments
    api_response = urllib.request.urlopen(conn, timeout=30).read()

    # Parse JSON response
    log_progress("parsing JSON response...")
    data = json.loads(api_response.decode("utf-8"))
    
    # Cache the data
    log_progress("caching data...")
    _save_cache(api_name, data)
    
    # Write timestamp for future conditional requests
    timestamp_str = time.strftime(
        "%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time())
    )
    _write_timestamp(api_name, timestamp_str)
    
    # Mark as ready
    _mark_ready(api_name)
    
    # Use consistent progress format for success message
    relay_count = len(data.get('relays', []))
    log_progress(f"successfully fetched {relay_count} relays from onionoo details API")
    
    return data


@handle_http_errors("onionoo uptime", _load_cache, _save_cache, _mark_ready, _mark_stale, 
                   allow_exit_on_304=False, critical=False)
def fetch_onionoo_uptime(onionoo_url="https://onionoo.torproject.org/uptime", progress_logger=None):
    """
    Fetch onionoo uptime data from the Tor Project's Onionoo API with smart caching.
    
    Caching strategy (configurable via constants at top of this file):
    - If cache is older than UPTIME_CACHE_MAX_AGE_HOURS: wait up to UPTIME_TIMEOUT_STALE_CACHE for fresh data
    - If cache is newer: use UPTIME_TIMEOUT_FRESH_CACHE, fallback to cache on timeout
    - This prevents excessive waiting while ensuring cache freshness over time
    
    Args:
        onionoo_url: URL to fetch uptime data from
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response from onionoo uptime API
    """
    api_name = "onionoo_uptime"
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
    
    # Check cache age AND validate cache can be loaded to determine timeout strategy
    # This prevents using short timeout when cache exists but is corrupted/unreadable
    cache_age = _cache_manager.get_cache_age(api_name)
    cache_max_age_seconds = UPTIME_CACHE_MAX_AGE_HOURS * 3600
    
    # Pre-load cache to verify it's valid (will be reused on timeout fallback)
    cached_data = None
    if cache_age is not None:
        cached_data = _load_cache(api_name)
        if cached_data is None:
            # Cache file exists but couldn't be loaded (corrupted/empty)
            # Treat as if no cache exists
            cache_age = None
            log_progress("cache file exists but is invalid, treating as no cache...")
    
    if cache_age is None:
        # No cache exists or cache is invalid, use longer timeout to establish initial cache
        timeout_seconds = UPTIME_TIMEOUT_STALE_CACHE
        timeout_minutes = timeout_seconds / 60
        log_progress(f"no valid cache exists, using {timeout_minutes:.0f} minute timeout for initial fetch...")
    elif cache_age >= cache_max_age_seconds:
        # Cache is stale (>= threshold), wait longer to refresh
        cache_hours = cache_age / 3600
        timeout_seconds = UPTIME_TIMEOUT_STALE_CACHE
        timeout_minutes = timeout_seconds / 60
        log_progress(f"cache is {cache_hours:.1f} hours old (>={UPTIME_CACHE_MAX_AGE_HOURS}h), using {timeout_minutes:.0f} minute timeout to refresh...")
    else:
        # Cache is relatively fresh (< threshold), use short timeout and fallback to cache if needed
        cache_minutes = cache_age / 60
        timeout_seconds = UPTIME_TIMEOUT_FRESH_CACHE
        log_progress(f"cache is {cache_minutes:.1f} minutes old (<{UPTIME_CACHE_MAX_AGE_HOURS}h), using {timeout_seconds} second timeout...")
    
    # Check for conditional request timestamp
    prev_timestamp = _read_timestamp(api_name)
    
    if prev_timestamp:
        headers = {"If-Modified-Since": prev_timestamp}
        conn = urllib.request.Request(onionoo_url, headers=headers)
    else:
        conn = urllib.request.Request(onionoo_url)

    # Try to fetch with timeout, fallback to cache on timeout
    try:
        api_response = urllib.request.urlopen(conn, timeout=timeout_seconds).read()
    except (socket.timeout, TimeoutError, urllib.error.URLError) as e:
        # Check if this is a timeout-related exception
        is_timeout = (
            isinstance(e, (socket.timeout, TimeoutError)) or 
            (isinstance(e, urllib.error.URLError) and isinstance(e.reason, (socket.timeout, TimeoutError)))
        )
        
        if is_timeout:
            log_progress(f"request timed out after {timeout_seconds} seconds...")
            # Use pre-loaded cached_data if available (validated earlier)
            if cached_data:
                log_progress("using cached uptime data due to timeout")
                _mark_ready(api_name)
                return cached_data
            else:
                log_progress("no cached data available after timeout")
                _mark_stale(api_name, f"Timeout after {timeout_seconds}s with no cache")
                return None
        else:
            # Re-raise if it's a different URLError (not a timeout)
            raise

    log_progress("parsing JSON response...")

    # Parse JSON response
    data = json.loads(api_response.decode("utf-8"))
    
    # Cache the data
    log_progress("caching data...")
    _save_cache(api_name, data)
    
    # Write timestamp for future conditional requests
    timestamp_str = time.strftime(
        "%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time())
    )
    _write_timestamp(api_name, timestamp_str)
    
    # Mark as ready
    _mark_ready(api_name)
    
    # Use consistent progress format for success message
    relay_count = len(data.get('relays', []))
    log_progress(f"successfully fetched {relay_count} relays from onionoo uptime API")
    return data


@handle_http_errors("onionoo historical bandwidth", _load_cache, _save_cache, _mark_ready, _mark_stale, 
                   allow_exit_on_304=False, critical=False)
def fetch_onionoo_bandwidth(onionoo_url="https://onionoo.torproject.org/bandwidth", cache_hours=12, progress_logger=None):
    """
    Fetch onionoo historical bandwidth data from the Tor Project's Onionoo API.
    Implements configurable cache refresh logic - only fetches if cache is older than specified hours.
    
    Args:
        onionoo_url: URL to fetch historical bandwidth data from
        cache_hours: Hours to cache historical bandwidth data before refreshing (default: 12)
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response from onionoo historical bandwidth API or cached data
    """
    api_name = "onionoo_bandwidth"
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
    
    # Convert hours to seconds for cache age comparison
    cache_seconds = cache_hours * 3600
    
    # Check cache age first - only refresh if older than specified hours
    cache_age = _cache_manager.get_cache_age(api_name)
    if cache_age is not None and cache_age < cache_seconds:
        log_progress(f"using cached historical bandwidth data (less than {cache_hours} hours old)")
        cached_data = _load_cache(api_name)
        if cached_data:
            _mark_ready(api_name)
            relay_count = len(cached_data.get('relays', []))
            log_progress(f"loaded {relay_count} relays from historical bandwidth cache")
            return cached_data
    
    # Cache is stale or doesn't exist, fetch new data
    log_progress(f"fetching fresh historical bandwidth data (cache older than {cache_hours} hours)")
    
    # Check for conditional request timestamp
    prev_timestamp = _read_timestamp(api_name)
    
    if prev_timestamp:
        headers = {"If-Modified-Since": prev_timestamp}
        conn = urllib.request.Request(onionoo_url, headers=headers)
    else:
        conn = urllib.request.Request(onionoo_url)

    # Add timeout to prevent hanging in CI environments
    api_response = urllib.request.urlopen(conn, timeout=30).read()

    log_progress("parsing JSON response...")

    # Parse JSON response
    data = json.loads(api_response.decode("utf-8"))
    
    # Cache the data
    log_progress("caching historical bandwidth data...")
    _save_cache(api_name, data)
    
    # Write timestamp for future conditional requests
    timestamp_str = time.strftime(
        "%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time())
    )
    _write_timestamp(api_name, timestamp_str)
    
    # Mark as ready
    _mark_ready(api_name)
    
    # Use consistent progress format for success message
    relay_count = len(data.get('relays', []))
    log_progress(f"successfully fetched {relay_count} relays from onionoo historical bandwidth API")
    return data


@handle_http_errors("AROI validation", _load_cache, _save_cache, _mark_ready, _mark_stale,
                   allow_exit_on_304=False, critical=False)
def fetch_aroi_validation(aroi_url="https://aroivalidator.1aeo.com/latest.json", progress_logger=None):
    """
    Fetch AROI validation data from aroivalidator.1aeo.com API.
    
    Args:
        aroi_url: URL to fetch AROI validation data from
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response with AROI validation data
    """
    api_name = "aroi_validation"
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
        else:
            print(message)
    
    # Check if we have cached data less than 1 hour old
    cache_path = os.path.join(CACHE_DIR, "aroi_validation_cache.json")
    if os.path.exists(cache_path):
        cache_age = time.time() - os.path.getmtime(cache_path)
        if cache_age < 3600:  # 1 hour in seconds
            log_progress(f"using cached AROI validation data (less than 1 hour old)")
            cached_data = _load_cache(api_name)
            if cached_data:
                validation_count = len(cached_data.get('results', []))
                log_progress(f"loaded {validation_count} relay validations from cache")
                _mark_ready(api_name)
                return cached_data
    
    # Fetch fresh data
    log_progress(f"fetching fresh AROI validation data")
    req = urllib.request.Request(aroi_url, headers={'User-Agent': 'Allium/1.0'})
    api_response = urllib.request.urlopen(req, timeout=30).read()
    
    log_progress("parsing JSON response...")
    data = json.loads(api_response.decode('utf-8'))
    
    # Validate structure
    required_keys = ['metadata', 'statistics', 'results']
    if not all(key in data for key in required_keys):
        log_progress("warning: invalid AROI validation data structure")
        return None
    
    # Cache the data
    log_progress("caching AROI validation data...")
    _save_cache(api_name, data)
    _mark_ready(api_name)
    
    validation_count = len(data.get('results', []))
    log_progress(f"successfully fetched {validation_count} relay validations from AROI validator API")
    
    return data


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