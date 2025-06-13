"""
Shared progress logging utilities for allium.

This module provides consistent progress logging functionality across different
components, including memory usage reporting and time formatting.
"""

import time
import sys
import os
import resource


def get_memory_usage():
    """
    Get current memory usage information.
    
    Returns:
        str: Formatted memory usage string
    """
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        peak_kb = usage.ru_maxrss
        if sys.platform == 'darwin':
            peak_kb = peak_kb / 1024
        
        current_rss_kb = None
        try:
            with open('/proc/self/status', 'r') as f:
                for line in f:
                    if line.startswith('VmRSS:'):
                        current_rss_kb = int(line.split()[1])
                        break
        except (FileNotFoundError, PermissionError, ValueError):
            current_rss_kb = peak_kb
        
        current_mb = (current_rss_kb or peak_kb) / 1024
        peak_mb = peak_kb / 1024
        
        if current_rss_kb and current_rss_kb != peak_kb:
            return f"RSS: {current_mb:.1f}MB, Peak: {peak_mb:.1f}MB"
        else:
            return f"Peak RSS: {peak_mb:.1f}MB"
    except Exception as e:
        return f"Memory: unavailable ({e})"


def log_progress(message, start_time, progress_step, total_steps, progress_enabled=True):
    """
    Log progress message with consistent formatting.
    
    Args:
        message (str): Progress message to display
        start_time (float): Start time timestamp
        progress_step (int): Current progress step
        total_steps (int): Total number of steps
        progress_enabled (bool): Whether progress logging is enabled
    """
    if not progress_enabled:
        return
        
    try:
        elapsed_time = time.time() - start_time
        memory_info = get_memory_usage()
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(elapsed_time))}] [{progress_step}/{total_steps}] [{memory_info}] Progress: {message}")
    except Exception:
        # Fallback if memory usage fails
        elapsed_time = time.time() - start_time
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(elapsed_time))}] [{progress_step}/{total_steps}] [Memory: N/A] Progress: {message}") 