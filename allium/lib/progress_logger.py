"""
Unified progress logging system.

This module provides the single ProgressLogger class used for all progress
output. One instance is created in allium.py and threaded through
coordinator → relays → page_writer/site_generator, so step numbering is
globally consistent across the whole run.
"""

import time
import threading
from .progress import log_progress

# Thread-safe lock for progress step increment to prevent race conditions
_step_lock = threading.Lock()


class ProgressLogger:
    """
    Unified progress logger that manages step counting and consistent formatting.

    Instances hold only primitives (floats/ints/bools/dict), so they stay
    picklable for multiprocessing workers; the increment lock is module-level.
    """

    def __init__(self, start_time=None, total_steps=53, progress_enabled=True):
        """
        Initialize the progress logger.

        Args:
            start_time: Start time for elapsed calculation (defaults to current time)
            total_steps: Total number of expected steps
            progress_enabled: Whether progress logging is enabled
        """
        self.start_time = start_time or time.time()
        self.progress_step = 0
        self.total_steps = total_steps
        self.progress_enabled = progress_enabled
        self.section_start_times = {}

    def log(self, message, increment_step=True):
        """
        Log a progress message with optional step increment.

        Thread-safe: Uses a lock to ensure step increment and logging are atomic.
        This prevents race conditions where multiple threads could increment the
        counter and log with inconsistent step numbers or timestamps.

        Args:
            message: Progress message to display
            increment_step: Whether to increment the step counter (default: True)
        """
        with _step_lock:
            if increment_step:
                self.progress_step += 1
            # Capture step value while holding lock to ensure consistency
            current_step = self.progress_step

        log_progress(message, self.start_time, current_step, self.total_steps, self.progress_enabled)

    def log_without_increment(self, message):
        """
        Log a progress message without incrementing the step counter.

        Args:
            message: Progress message to display
        """
        self.log(message, increment_step=False)

    def start_section(self, section_name):
        """
        Record the start of a major processing section.

        Args:
            section_name: Name of the section (e.g., "API Fetching", "Page Generation")
        """
        if not section_name:
            return
        self.section_start_times[section_name] = time.time()
        self.log(f"═══ SECTION: {section_name} ═══ [STARTING]")

    def end_section(self, section_name):
        """
        Record the completion of a major processing section and log elapsed time.

        Args:
            section_name: Name of the section to end
        """
        if not section_name:
            return
        start_time = self.section_start_times.pop(section_name, self.start_time)
        elapsed = time.time() - start_time
        self.log(f"═══ SECTION: {section_name} ═══ [COMPLETE in {elapsed:.1f}s]")
