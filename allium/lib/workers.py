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
    Fetch onionoo uptime data from the Tor Project's Onionoo API
    
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