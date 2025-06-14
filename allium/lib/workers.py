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


def _save_cache(api_name, data):
    """
    Save API data to cache file
    
    Args:
        api_name: Name of the API (e.g., 'onionoo_details')
        data: Data to cache (will be JSON serialized)
    """
    cache_file = os.path.join(CACHE_DIR, f"{api_name}.json")
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save cache for {api_name}: {e}")


def _load_cache(api_name):
    """
    Load API data from cache file
    
    Args:
        api_name: Name of the API (e.g., 'onionoo_details')
        
    Returns:
        Cached data or None if not available
    """
    cache_file = os.path.join(CACHE_DIR, f"{api_name}.json")
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load cache for {api_name}: {e}")
    return None


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


def _save_state():
    """Save worker state to file (called with lock held)"""
    try:
        state_data = {
            "workers": _worker_status,
            "last_updated": time.time()
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save state: {e}")


def _load_state():
    """Load worker state from file"""
    global _worker_status
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state_data = json.load(f)
                _worker_status = state_data.get("workers", {})
    except Exception as e:
        print(f"Warning: Failed to load state: {e}")
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


def _write_timestamp(api_name, timestamp_str):
    """
    Store encoded timestamp for conditional requests
    
    Args:
        api_name: Name of the API
        timestamp_str: Formatted timestamp string
    """
    timestamp_file = os.path.join(CACHE_DIR, f"{api_name}_timestamp.txt")
    try:
        with open(timestamp_file, "w", encoding="utf-8") as f:
            f.write(timestamp_str)
    except Exception as e:
        print(f"Warning: Failed to save timestamp for {api_name}: {e}")


def _read_timestamp(api_name):
    """
    Read stored timestamp for conditional requests
    
    Args:
        api_name: Name of the API
        
    Returns:
        str: Timestamp string or None if not available
    """
    timestamp_file = os.path.join(CACHE_DIR, f"{api_name}_timestamp.txt")
    try:
        if os.path.exists(timestamp_file):
            with open(timestamp_file, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception as e:
        print(f"Warning: Failed to read timestamp for {api_name}: {e}")
    return None


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
    
    try:
        # Check for conditional request timestamp
        prev_timestamp = _read_timestamp(api_name)
        
        if prev_timestamp:
            headers = {"If-Modified-Since": prev_timestamp}
            conn = urllib.request.Request(onionoo_url, headers=headers)
        else:
            conn = urllib.request.Request(onionoo_url)

        try:
            # Add timeout to prevent hanging in CI environments
            api_response = urllib.request.urlopen(conn, timeout=30).read()
        except urllib.error.HTTPError as err:
            if err.code == 304:
                # No update since last run - use cached data
                log_progress("no onionoo update since last run, using cached data...")
                cached_data = _load_cache(api_name)
                if cached_data:
                    _mark_ready(api_name)
                    return cached_data
                else:
                    # No cache available, this is a problem
                    log_progress("no onionoo update since last run, dying peacefully...")
                    sys.exit(1)
            else:
                log_progress(f"HTTP error fetching onionoo data: {err.code}")
                raise err
        except urllib.error.URLError as err:
            log_progress(f"network error fetching onionoo data: {err}")
            log_progress("check your internet connection and try again")
            log_progress("in CI environments, this might be a temporary network issue")
            raise err

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
        
    except Exception as e:
        error_msg = f"Failed to fetch onionoo details: {str(e)}"
        log_progress(f"error: {error_msg}")
        _mark_stale(api_name, error_msg)
        
        # Try to return cached data as fallback
        cached_data = _load_cache(api_name)
        if cached_data:
            log_progress("using cached onionoo data as fallback")
            return cached_data
        else:
            log_progress("no cached data available, cannot continue")
            return None


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
    
    try:
        # Check for conditional request timestamp
        prev_timestamp = _read_timestamp(api_name)
        
        if prev_timestamp:
            headers = {"If-Modified-Since": prev_timestamp}
            conn = urllib.request.Request(onionoo_url, headers=headers)
        else:
            conn = urllib.request.Request(onionoo_url)

        try:
            # Add timeout to prevent hanging in CI environments
            api_response = urllib.request.urlopen(conn, timeout=30).read()
        except urllib.error.HTTPError as err:
            if err.code == 304:
                # No update since last run - use cached data
                log_progress("no onionoo uptime update since last run, using cached data...")
                cached_data = _load_cache(api_name)
                if cached_data:
                    _mark_ready(api_name)
                    return cached_data
                else:
                    # No cache available, this is a problem
                    log_progress("no onionoo uptime update since last run and no cache, skipping uptime data...")
                    # Mark as stale but don't exit - uptime is not critical
                    _mark_stale(api_name, "No cached uptime data available")
                    return None
            else:
                log_progress(f"HTTP error fetching onionoo uptime data: {err.code}")
                raise err
        except urllib.error.URLError as err:
            log_progress(f"network error fetching onionoo uptime data: {err}")
            log_progress("check your internet connection and try again")
            log_progress("in CI environments, this might be a temporary network issue")
            raise err

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
        
    except Exception as e:
        error_msg = f"Failed to fetch onionoo uptime: {str(e)}"
        log_progress(f"error: {error_msg}")
        _mark_stale(api_name, error_msg)
        
        # Try to return cached data as fallback
        cached_data = _load_cache(api_name)
        if cached_data:
            log_progress("using cached onionoo data as fallback")
            return cached_data
        else:
            log_progress("no cached data available, continuing without uptime data")
            return None


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