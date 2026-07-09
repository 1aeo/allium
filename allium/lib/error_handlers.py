"""
Centralized error handling decorators and utilities.

This module provides decorators and utilities to eliminate error handling duplication
across workers.py, coordinator.py, and relays.py files.
"""

import functools
import json
import urllib.error
from typing import Any, Callable


def handle_http_errors(cache_key: str, display_name: str, cache_loader: Callable,
                      cache_saver: Callable, mark_ready: Callable, mark_stale: Callable,
                      allow_exit_on_304: bool = False, critical: bool = True):
    """
    Decorator for handling HTTP errors in API worker functions.

    Args:
        cache_key: Machine key used for cache files and worker status
            (must match APIConfig.api_name, e.g. 'onionoo_details')
        display_name: Human-readable API name for log messages only
        cache_loader: Function to load cached data
        cache_saver: Function to save cached data
        mark_ready: Function to mark worker as ready
        mark_stale: Function to mark worker as stale
        allow_exit_on_304: Whether to exit on HTTP 304 when no cache
        critical: Whether this API is critical (affects exit behavior)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract progress logger from args
            progress_logger = None
            if len(args) > 1 and callable(args[1]):
                progress_logger = args[1]
            
            def log_progress(message):
                if progress_logger:
                    progress_logger(message)
                else:
                    print(message)
            
            try:
                return func(*args, **kwargs)
                
            except urllib.error.HTTPError as err:
                if err.code == 304:
                    # No update since last run - use cached data
                    log_progress(f"no {display_name} update since last run, using cached data...")
                    cached_data = cache_loader(cache_key)
                    if cached_data:
                        mark_ready(cache_key)
                        return cached_data
                    else:
                        if allow_exit_on_304:
                            log_progress(f"no {display_name} update since last run, dying peacefully...")
                            # Don't call sys.exit(1) from worker threads - it only kills the thread
                            # Instead, mark as stale and return None to let coordinator handle gracefully
                            mark_stale(cache_key, f"No cached {display_name} data available (304 with no cache)")
                            return None
                        else:
                            log_progress(f"no {display_name} update since last run and no cache, skipping {display_name} data...")
                            mark_stale(cache_key, f"No cached {display_name} data available")
                            return None
                else:
                    log_progress(f"HTTP error fetching {display_name} data: {err.code}")
                    raise err
                    
            except urllib.error.URLError as err:
                log_progress(f"network error fetching {display_name} data: {err}")
                log_progress("check your internet connection and try again")
                log_progress("in CI environments, this might be a temporary network issue")
                raise err
                
            except Exception as e:
                error_msg = f"Failed to fetch {display_name}: {str(e)}"
                log_progress(f"error: {error_msg}")
                mark_stale(cache_key, error_msg)
                
                # Try to return cached data as fallback
                cached_data = cache_loader(cache_key)
                if cached_data:
                    log_progress(f"using cached {display_name} data as fallback")
                    return cached_data
                else:
                    if critical:
                        log_progress("no cached data available, cannot continue")
                    else:
                        log_progress(f"no cached data available, continuing without {display_name} data")
                    return None
                    
        return wrapper
    return decorator


def handle_file_io_errors(operation: str, context: str = ""):
    """
    Decorator for handling file I/O errors consistently.
    
    Args:
        operation: Description of the operation (e.g., "save cache", "load cache")
        context: Additional context for error messages
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context_str = f" for {context}" if context else ""
                print(f"Warning: Failed to {operation}{context_str}: {e}")
                return None
        return wrapper
    return decorator


def handle_json_errors(operation: str = "parse JSON", default_return: Any = None):
    """
    Decorator for handling JSON parsing errors consistently.
    
    Args:
        operation: Description of the operation
        default_return: Value to return on error
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Warning: Failed to {operation}: {e}")
                return default_return
            except Exception as e:
                print(f"Warning: Unexpected error during {operation}: {e}")
                return default_return
        return wrapper
    return decorator


def handle_calculation_errors(operation: str = "calculation", default_return: Any = None, 
                             log_errors: bool = True):
    """
    Decorator for handling calculation errors in relays.py and other modules.
    
    Args:
        operation: Description of the operation
        default_return: Value to return on error
        log_errors: Whether to log errors
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    print(f"Warning: {operation} failed: {str(e)}")
                return default_return
        return wrapper
    return decorator

