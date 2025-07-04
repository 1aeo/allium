"""
Unified progress logging system to eliminate duplication across the codebase.

This module provides a centralized ProgressLogger class that consolidates the three
different progress logging implementations found in allium.py, coordinator.py, and relays.py.
"""

import time
from .progress import log_progress


class ProgressLogger:
    """
    Unified progress logger that manages step counting and consistent formatting.
    
    Consolidates the duplicate progress logging logic from:
    - log_step_progress() in allium.py
    - _log_progress_with_step_increment() in coordinator.py  
    - _log_progress() in relays.py
    """
    
    def __init__(self, start_time=None, progress_step=0, total_steps=34, progress_enabled=True):
        """
        Initialize the progress logger.
        
        Args:
            start_time: Start time for elapsed calculation (defaults to current time)
            progress_step: Initial progress step counter
            total_steps: Total number of expected steps
            progress_enabled: Whether progress logging is enabled
        """
        self.start_time = start_time or time.time()
        self.progress_step = progress_step
        self.total_steps = total_steps
        self.progress_enabled = progress_enabled
    
    def log(self, message, increment_step=True):
        """
        Log a progress message with optional step increment.
        
        Args:
            message: Progress message to display
            increment_step: Whether to increment the step counter (default: True)
        """
        if increment_step:
            self.progress_step += 1
        
        log_progress(message, self.start_time, self.progress_step, self.total_steps, self.progress_enabled)
    
    def log_without_increment(self, message):
        """
        Log a progress message without incrementing the step counter.
        
        Args:
            message: Progress message to display
        """
        self.log(message, increment_step=False)
    
    def log_with_increment(self, message):
        """
        Log a progress message and increment the step counter.
        
        Args:
            message: Progress message to display
        """
        self.log(message, increment_step=True)
    
    def get_current_step(self):
        """Get the current progress step."""
        return self.progress_step
    
    def set_step(self, step):
        """Set the current progress step."""
        self.progress_step = step
    
    def increment_step(self):
        """Increment the progress step without logging."""
        self.progress_step += 1
    
    def update_from_other_logger(self, other_logger):
        """
        Update this logger's step count from another ProgressLogger instance.
        
        Args:
            other_logger: Another ProgressLogger instance to sync from
        """
        if isinstance(other_logger, ProgressLogger):
            self.progress_step = other_logger.progress_step
        else:
            # Handle cases where we're passed a simple step counter
            if hasattr(other_logger, 'progress_step'):
                self.progress_step = other_logger.progress_step
    
    def create_child_logger(self, api_name=""):
        """
        Create a child logger that includes an API name prefix in messages.
        
        Args:
            api_name: Name to prefix in log messages
            
        Returns:
            Function that can be used as a progress logger with API prefix
        """
        def child_log(message):
            if api_name:
                formatted_message = f"{api_name} - {message}"
            else:
                formatted_message = message
            self.log_with_increment(formatted_message)
        
        return child_log


def create_progress_logger(start_time=None, progress_step=0, total_steps=34, progress_enabled=True):
    """
    Factory function to create a ProgressLogger instance.
    
    Args:
        start_time: Start time for elapsed calculation (defaults to current time)
        progress_step: Initial progress step counter
        total_steps: Total number of expected steps
        progress_enabled: Whether progress logging is enabled
        
    Returns:
        ProgressLogger instance
    """
    return ProgressLogger(start_time, progress_step, total_steps, progress_enabled)


# Legacy compatibility functions that delegate to ProgressLogger
def log_step_progress(message, start_time, progress_step, total_steps, progress_enabled, increment=True):
    """
    Legacy compatibility function for allium.py log_step_progress.
    
    Note: This returns the updated progress_step for backwards compatibility.
    """
    logger = ProgressLogger(start_time, progress_step, total_steps, progress_enabled)
    logger.log(message, increment_step=increment)
    return logger.progress_step


def log_progress_with_step_increment(message, logger):
    """
    Legacy compatibility function for coordinator.py _log_progress_with_step_increment.
    
    Args:
        message: Progress message
        logger: ProgressLogger instance to use
    """
    logger.log_with_increment(message)