"""
File: coordinator.py

Simple coordinator for managing API workers and coordinating with main allium logic.
Phase 1 implementation: basic threading coordination between workers and the main allium logic.
Phase 2 implementation: multiple API support, threading, and incremental rendering.
"""

import threading
import time
from .workers import (
    fetch_onionoo_details, fetch_onionoo_uptime, 
    get_worker_status, get_all_worker_status
)
from .relays import Relays
from .progress import log_progress


class Coordinator:
    """
    Coordinator for managing API workers with threading support.
    Phase 1: Basic threading support for onionoo with backwards compatibility.
    Phase 2: Multiple API support with incremental rendering.
    """
    
    def __init__(self, output_dir, onionoo_details_url, onionoo_uptime_url, use_bits=False, progress=False, start_time=None, progress_step=0, total_steps=20, enabled_apis='all'):
        self.output_dir = output_dir
        self.onionoo_details_url = onionoo_details_url
        self.onionoo_uptime_url = onionoo_uptime_url
        self.use_bits = use_bits
        self.progress = progress
        self.start_time = start_time or time.time()
        self.progress_step = progress_step
        self.total_steps = total_steps
        self.enabled_apis = enabled_apis
        
        # Worker management
        self.workers = {}
        self.worker_data = {}
        self.worker_threads = []
        
        # API workers to run (Phase 2: multiple APIs)
        # Build API workers list based on enabled APIs
        self.api_workers = []
        
        # Always include details API (required for core functionality)
        self.api_workers.append(("onionoo_details", fetch_onionoo_details, [self.onionoo_details_url]))
        
        # Include uptime API only if 'all' is selected (details + uptime)
        if self.enabled_apis == 'all':
            self.api_workers.append(("onionoo_uptime", fetch_onionoo_uptime, [self.onionoo_uptime_url]))
        
    def _log_progress(self, message):
        """Log progress message using shared progress utility"""
        log_progress(message, self.start_time, self.progress_step, self.total_steps, self.progress)
    
    def _run_worker(self, api_name, worker_func, args):
        """Run a single API worker in a thread"""
        try:
            self._log_progress(f"Starting {api_name} worker...")
            result = worker_func(*args)
            self.worker_data[api_name] = result
            self._log_progress(f"Completed {api_name} worker")
        except Exception as e:
            self._log_progress(f"Error in {api_name} worker: {str(e)}")
            self.worker_data[api_name] = None

    def fetch_all_apis_threaded(self):
        """
        Fetch data from all APIs using threading (Phase 2 implementation)
        """
        if self.progress:
            self._log_progress("Starting threaded API fetching...")
        
        # Start all API workers in threads
        for api_name, worker_func, args in self.api_workers:
            thread = threading.Thread(
                target=self._run_worker,
                args=(api_name, worker_func, args),
                name=f"Worker-{api_name}"
            )
            thread.start()
            self.worker_threads.append((api_name, thread))
        
        # Wait for all threads to complete
        for api_name, thread in self.worker_threads:
            thread.join()
            if self.progress:
                self._log_progress(f"Joined {api_name} worker thread")
        
        if self.progress:
            self._log_progress("All API workers completed")
        
        return self.worker_data
    def fetch_onionoo_data(self):
        """
        Fetch onionoo data using workers system.
        Phase 2: Uses threaded approach for multiple APIs, but returns only details for compatibility.
        """
        if self.progress:
            self._log_progress("Fetching onionoo data using workers system...")
        
        # For Phase 2, fetch all APIs but prioritize details for backward compatibility
        all_data = self.fetch_all_apis_threaded()
        
        # Return the details data for backward compatibility
        details_data = all_data.get('onionoo_details')
        if details_data:
            if self.progress:
                self._log_progress(f"Successfully fetched {len(details_data.get('relays', []))} relays from onionoo")
            return details_data
        else:
            if self.progress:
                self._log_progress("Failed to fetch onionoo details data")
            return None

    def get_uptime_data(self):
        """
        Get uptime data if available (Phase 2 addition)
        """
        return self.worker_data.get('onionoo_uptime')

    def get_consensus_health_data(self):
        """
        Get consensus health data if available (Future API)
        """
        return self.worker_data.get('consensus_health')

    def get_collector_data(self):
        """
        Get collector data if available (Future API)
        """
        return self.worker_data.get('collector')

    def create_relay_set(self, relay_data):
        """
        Create Relays instance with fetched data.
        """
        if self.progress:
            self._log_progress("Creating relay set with fetched data...")
        
        relay_set = Relays(
            output_dir=self.output_dir,
            onionoo_url=self.onionoo_details_url,
            relay_data=relay_data,  # Required parameter
            use_bits=self.use_bits,
            progress=self.progress,
            start_time=self.start_time,
            progress_step=self.progress_step,
            total_steps=self.total_steps
        )
        
        if relay_set.json is None:
            if self.progress:
                self._log_progress("Failed to create relay set")
            return None
        
        # Phase 2: Attach additional API data to relay set (direct assignment)
        relay_set.uptime_data = self.get_uptime_data()
        relay_set.consensus_health_data = self.get_consensus_health_data()
        relay_set.collector_data = self.get_collector_data()
        
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
def create_relay_set_with_coordinator(output_dir, onionoo_details_url, onionoo_uptime_url, use_bits=False, progress=False, start_time=None, progress_step=0, total_steps=20, enabled_apis='all'):
    """
    Create a relay set using the coordinator system.
    Phase 2: Support for multiple APIs with threading.
    """
    # Provide default start_time if None is passed
    if start_time is None:
        start_time = time.time()
        
    coordinator = Coordinator(
        output_dir=output_dir,
        onionoo_details_url=onionoo_details_url,
        onionoo_uptime_url=onionoo_uptime_url,
        use_bits=use_bits,
        progress=progress,
        start_time=start_time,
        progress_step=progress_step,
        total_steps=total_steps,
        enabled_apis=enabled_apis
    )
    
    return coordinator.get_relay_set() 