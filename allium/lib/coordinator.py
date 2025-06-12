"""
File: coordinator.py

Simple coordinator for managing API workers and coordinating with main allium logic.
Phase 1 implementation: basic threading coordination between workers and the main allium logic.
"""

import threading
import time
from .workers import fetch_onionoo_details, get_worker_status, get_all_worker_status
from .relays import Relays


class Coordinator:
    """
    Simple coordinator for managing API workers.
    Phase 1: Basic threading support for onionoo with backwards compatibility.
    """
    
    def __init__(self, output_dir, onionoo_url, use_bits=False, progress=False, start_time=None, progress_step=0, total_steps=20):
        self.output_dir = output_dir
        self.onionoo_url = onionoo_url
        self.use_bits = use_bits
        self.progress = progress
        self.start_time = start_time or time.time()
        self.progress_step = progress_step
        self.total_steps = total_steps
        
        # Worker management
        self.workers = {}
        self.worker_data = {}
        
    def _log_progress(self, message):
        """Log progress message in the same format as main allium.py"""
        if self.progress:
            try:
                # Import the get_memory_usage function from main allium.py
                import sys
                import os
                import resource
                
                def get_memory_usage():
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
                
                elapsed_time = time.time() - self.start_time
                print(f"[{time.strftime('%H:%M:%S', time.gmtime(elapsed_time))}] [{self.progress_step}/{self.total_steps}] [{get_memory_usage()}] Progress: {message}")
            except Exception:
                # Fallback if memory usage fails
                elapsed_time = time.time() - self.start_time
                print(f"[{time.strftime('%H:%M:%S', time.gmtime(elapsed_time))}] [{self.progress_step}/{self.total_steps}] [Memory: N/A] Progress: {message}")
    
    def fetch_onionoo_data(self):
        """
        Fetch onionoo data using workers system.
        Returns data for creating Relays instance.
        """
        if self.progress:
            self._log_progress("Fetching onionoo data using workers system...")
        
        # For Phase 1, we'll just use the workers system to fetch onionoo details
        # In future phases, this will coordinate multiple APIs
        try:
            data = fetch_onionoo_details(self.onionoo_url)
            if data:
                if self.progress:
                    self._log_progress(f"Successfully fetched {len(data.get('relays', []))} relays from onionoo")
                return data
            else:
                if self.progress:
                    self._log_progress("Failed to fetch onionoo data")
                return None
        except Exception as e:
            if self.progress:
                self._log_progress(f"Error fetching onionoo data: {str(e)}")
            return None
    
    def create_relay_set(self, relay_data):
        """
        Create Relays instance with fetched data.
        """
        if self.progress:
            self._log_progress("Creating relay set with fetched data...")
        
        relay_set = Relays(
            output_dir=self.output_dir,
            onionoo_url=self.onionoo_url,
            use_bits=self.use_bits,
            progress=self.progress,
            start_time=self.start_time,
            progress_step=self.progress_step,
            total_steps=self.total_steps,
            relay_data=relay_data  # Use new pattern
        )
        
        if relay_set.json is None:
            if self.progress:
                self._log_progress("Failed to create relay set")
            return None
        
        if self.progress:
            self._log_progress("Relay set created successfully")
        
        return relay_set
    
    def get_relay_set(self):
        """
        Main entry point: fetch data and create Relays instance.
        This method provides the same interface as the original Relays() constructor.
        """
        # Fetch data using workers
        relay_data = self.fetch_onionoo_data()
        if relay_data is None:
            return None
        
        # Create Relays instance with the data
        return self.create_relay_set(relay_data)
    
    def get_worker_status_summary(self):
        """Get summary of all worker statuses for debugging/monitoring"""
        statuses = get_all_worker_status()
        return {
            "worker_count": len(statuses),
            "ready_count": len([s for s in statuses.values() if s.get("status") == "ready"]),
            "stale_count": len([s for s in statuses.values() if s.get("status") == "stale"]),
            "workers": statuses
        }


# For backwards compatibility, provide a simple function that mimics the original Relays constructor
def create_relay_set_with_coordinator(output_dir, onionoo_url, use_bits=False, progress=False, start_time=None, progress_step=0, total_steps=20):
    """
    Backwards compatible function that uses the coordinator internally.
    This allows allium.py to use the new system with minimal changes.
    """
    coordinator = Coordinator(
        output_dir=output_dir,
        onionoo_url=onionoo_url,
        use_bits=use_bits,
        progress=progress,
        start_time=start_time,
        progress_step=progress_step,
        total_steps=total_steps
    )
    
    return coordinator.get_relay_set() 