"""
Centralized error handling decorators and utilities.

This module provides decorators and utilities to eliminate error handling duplication
across workers.py, coordinator.py, and relays.py files.
"""

import functools
import json
from typing import Any, Callable


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

