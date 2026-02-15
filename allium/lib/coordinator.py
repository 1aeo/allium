"""
File: coordinator.py

Simple coordinator for managing API workers and coordinating with main allium logic.
Phase 1 implementation: basic threading coordination between workers and the main allium logic.
Phase 2 implementation: multiple API support, threading, and incremental rendering.
"""

import threading
import time
from .workers import (
    fetch_onionoo_details, fetch_onionoo_uptime, fetch_onionoo_bandwidth,
    fetch_aroi_validation, fetch_collector_consensus_data, fetch_consensus_health,
    get_worker_status, get_all_worker_status
)
from .relays import Relays
from .progress import log_progress
from .progress_logger import ProgressLogger
from .error_handlers import handle_worker_errors, handle_calculation_errors


class Coordinator:
    """
    Coordinator for managing API workers with threading support.
    Phase 1: Basic threading support for onionoo with backwards compatibility.
    Phase 2: Multiple API support with incremental rendering.
    """
    
    def __init__(self, output_dir, onionoo_details_url, onionoo_uptime_url, onionoo_bandwidth_url, aroi_url, bandwidth_cache_hours, use_bits=False, progress=False, start_time=None, progress_step=0, total_steps=53, enabled_apis='all', filter_downtime_days=7, base_url='', progress_logger=None, mp_workers=4):
        self.output_dir = output_dir
        self.onionoo_details_url = onionoo_details_url
        self.onionoo_uptime_url = onionoo_uptime_url
        self.onionoo_bandwidth_url = onionoo_bandwidth_url
        self.aroi_url = aroi_url
        self.bandwidth_cache_hours = bandwidth_cache_hours
        self.use_bits = use_bits
        self.progress = progress
        self.start_time = start_time or time.time()
        self.progress_step = progress_step
        self.total_steps = total_steps
        self.enabled_apis = enabled_apis
        self.filter_downtime_days = filter_downtime_days
        self.base_url = base_url
        self.mp_workers = mp_workers
        
        # Use injected progress logger or create new one
        if progress_logger is not None:
            self.progress_logger = progress_logger
            # Sync state from injected logger
            self.start_time = progress_logger.start_time
            self.progress_step = progress_logger.get_current_step()
            self.total_steps = progress_logger.total_steps
        else:
            self.progress_logger = ProgressLogger(self.start_time, self.progress_step, self.total_steps, self.progress)
        
        # Worker management
        self.workers = {}
        self.worker_data = {}
        self.worker_threads = []
        
        # API workers to run (Phase 2: multiple APIs)
        # Build API workers list based on enabled APIs
        self.api_workers = []
        
        # Always include details API (required for core functionality)
        self.api_workers.append(("onionoo_details", fetch_onionoo_details, [self.onionoo_details_url, self._log_progress]))
        
        # Include uptime API only if 'all' is selected (details + uptime)
        if self.enabled_apis == 'all':
            self.api_workers.append(("onionoo_uptime", fetch_onionoo_uptime, [self.onionoo_uptime_url, self._log_progress]))
            self.api_workers.append(("onionoo_bandwidth", fetch_onionoo_bandwidth, [self.onionoo_bandwidth_url, self.bandwidth_cache_hours, self._log_progress]))
            self.api_workers.append(("aroi_validation", fetch_aroi_validation, [self.aroi_url, self._log_progress]))
            
            # CollecTor consensus evaluation (Phase 1 feature)
            # Note: authorities parameter will be None initially, set after Onionoo fetch completes
            from .consensus import is_consensus_evaluation_enabled as collector_enabled
            if collector_enabled():
                self.api_workers.append(("collector_consensus", fetch_collector_consensus_data, [None, self._log_progress]))
        
    def _log_progress(self, message):
        """Log progress message using shared progress utility"""
        log_progress(message, self.start_time, self.progress_step, self.total_steps, self.progress)
    
    def _run_worker(self, api_name, worker_func, args):
        """Run a single API worker in a thread"""
        try:
            # Create API-specific progress logger that includes API name
            api_specific_logger = self._create_api_specific_logger(api_name)
            
            # Update args to use the API-specific logger
            args_with_api_logger = list(args)
            # Replace the last argument (progress_logger) with the API-specific logger
            args_with_api_logger[-1] = api_specific_logger
            
            # Log API-specific start message
            api_display_name = self._get_api_display_name(api_name)
            self._log_progress_with_step_increment(f"{api_display_name} - fetching onionoo data using workers system")
            
            result = worker_func(*args_with_api_logger)
            self.worker_data[api_name] = result
            if result is not None:
                self._log_progress_with_step_increment(f"{api_display_name} - completed successfully")
            else:
                self._log_progress_with_step_increment(f"{api_display_name} - warning: returned no data")
        except Exception as e:
            # Use centralized error handling approach
            api_display_name = self._get_api_display_name(api_name)
            self._log_progress_with_step_increment(f"{api_display_name} - error: {str(e)}")
            self.worker_data[api_name] = None
            
            # CI debugging with centralized approach
            import os
            if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
                print(f"🔧 CI Debug: {api_name} worker failed with: {e}")
                import traceback
                traceback.print_exc()

    def _get_api_display_name(self, api_name):
        """Get display name for API"""
        if api_name == "onionoo_details":
            return "Details API"
        elif api_name == "onionoo_uptime":
            return "Uptime API"
        elif api_name == "onionoo_bandwidth":
            return "Historical Bandwidth API"
        elif api_name == "aroi_validation":
            return "AROI Validation API"
        elif api_name == "collector_consensus":
            return "CollecTor Consensus API"
        elif api_name == "consensus_health":
            return "Authority Health API"
        else:
            return api_name.replace("_", " ").title()

    def _create_api_specific_logger(self, api_name):
        """Create a progress logger that includes API name in messages.
        
        These loggers are used for intermediate progress messages within API workers
        (cache status, parsing, etc.) and do NOT increment the step counter.
        Only the coordinator's explicit start/complete messages increment the counter,
        making the total step count predictable regardless of cache state.
        """
        api_display_name = self._get_api_display_name(api_name)
        
        def api_logger(message):
            # Format message with API name prefix but DON'T increment step
            # This keeps step count predictable (only start/complete increment)
            formatted_message = f"{api_display_name} - {message}"
            self._log_progress_without_increment(formatted_message)
        
        return api_logger

    def _log_progress_without_increment(self, message):
        """Log progress message without incrementing progress step (for intermediate messages)"""
        self.progress_logger.log_without_increment(message)

    def _log_progress_with_step_increment(self, message):
        """Log progress message and increment progress step"""
        self.progress_logger.log_with_increment(message)
        # Keep progress_step in sync for backwards compatibility
        self.progress_step = self.progress_logger.get_current_step()

    def fetch_all_apis_threaded(self):
        """
        Fetch data from all APIs using threading (Phase 2 implementation)
        """
        if self.progress:
            self.progress_logger.start_section("API Fetching")
            self._log_progress_with_step_increment("Starting threaded API fetching...")
        
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
            # Don't log thread join messages to avoid clutter
        
        if self.progress:
            self._log_progress_with_step_increment("All API workers completed")
            self.progress_logger.end_section("API Fetching")
        
        return self.worker_data

    def fetch_onionoo_data(self):
        """
        Fetch onionoo data using workers system.
        Phase 2: Uses threaded approach for multiple APIs, but returns only details for compatibility.
        """
        # No generic progress message here - the specific API messages are logged in _run_worker
        
        # For Phase 2, fetch all APIs but prioritize details for backward compatibility
        try:
            all_data = self.fetch_all_apis_threaded()
        except Exception as e:
            if self.progress:
                self._log_progress_with_step_increment(f"Error during threaded API fetching: {e}")
            print(f"❌ Error: Failed to fetch API data: {e}")
            print("🔧 This might be due to network connectivity issues")
            return None
        
        # Return the details data for backward compatibility
        details_data = all_data.get('onionoo_details')
        if details_data:
            return details_data
        else:
            if self.progress:
                self._log_progress_with_step_increment("Failed to fetch onionoo details data")
            print("❌ Error: No details data available from onionoo API")
            print("🔧 This might be due to:")
            print("   - Network connectivity issues")
            print("   - onionoo.torproject.org temporary unavailability")
            print("   - API rate limiting")
            return None

    def get_uptime_data(self):
        """
        Get uptime data if available (Phase 2 addition)
        """
        return self.worker_data.get('onionoo_uptime')

    def get_bandwidth_data(self):
        """
        Get historical bandwidth data if available
        """
        return self.worker_data.get('onionoo_bandwidth')

    def get_aroi_validation_data(self):
        """
        Get AROI validation data if available
        """
        return self.worker_data.get('aroi_validation')

    def get_consensus_health_data(self):
        """
        Get consensus health data if available.
        """
        return self.worker_data.get('consensus_health')

    def get_collector_data(self):
        """
        Get collector data if available (legacy)
        """
        return self.worker_data.get('collector')

    def get_collector_consensus_data(self):
        """
        Get CollecTor consensus data if available.
        Contains authority votes, relay index, flag thresholds.
        """
        return self.worker_data.get('collector_consensus')

    def create_relay_set(self, relay_data):
        """
        Create Relays instance with fetched data.
        
        The heavy lifting is split between Relays.__init__ (core processing from
        details API) and Relays.enrich_with_api_data() (secondary API enrichment).
        See enrich_with_api_data() docstring for the full pipeline overview.
        """
        if self.progress:
            self.progress_logger.start_section("Data Processing")
            self._log_progress_with_step_increment("Creating relay set with Details API data...")
        
        relay_set = Relays(
            output_dir=self.output_dir,
            onionoo_url=self.onionoo_details_url,
            relay_data=relay_data,
            use_bits=self.use_bits,
            progress=self.progress,
            start_time=self.start_time,
            progress_step=self.progress_step,
            total_steps=self.total_steps,
            filter_downtime_days=self.filter_downtime_days,
            base_url=self.base_url,
            progress_logger=self.progress_logger,
            mp_workers=self.mp_workers,
        )
        
        if relay_set.json is None:
            if self.progress:
                self._log_progress_with_step_increment("Failed to create relay set")
            return None
        
        # Enrich with secondary API data (uptime, bandwidth, AROI, collector)
        # Processing order and dependencies are documented in enrich_with_api_data()
        relay_set.enrich_with_api_data(
            uptime_data=self.get_uptime_data(),
            bandwidth_data=self.get_bandwidth_data(),
            aroi_validation_data=self.get_aroi_validation_data(),
            collector_consensus_data=self.get_collector_consensus_data(),
            consensus_health_data=self.get_consensus_health_data(),
        )
        
        # Sync progress state
        relay_set.progress_step = self.progress_step
        
        if self.progress:
            self._log_progress_with_step_increment("Relay set created successfully with Details API and Uptime API data")
            self.progress_logger.end_section("Data Processing")
        
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
def create_relay_set_with_coordinator(output_dir, onionoo_details_url, onionoo_uptime_url, onionoo_bandwidth_url, aroi_url, bandwidth_cache_hours, use_bits=False, progress=False, start_time=None, progress_step=0, total_steps=53, enabled_apis='all', filter_downtime_days=7, base_url='', progress_logger=None, mp_workers=4):
    """
    Create a relay set using the coordinator system.
    Phase 2: Support for multiple APIs with threading.
    """
    if start_time is None:
        start_time = time.time()
        
    coordinator = Coordinator(
        output_dir=output_dir,
        onionoo_details_url=onionoo_details_url,
        onionoo_uptime_url=onionoo_uptime_url,
        onionoo_bandwidth_url=onionoo_bandwidth_url,
        aroi_url=aroi_url,
        bandwidth_cache_hours=bandwidth_cache_hours,
        use_bits=use_bits,
        progress=progress,
        start_time=start_time,
        progress_step=progress_step,
        total_steps=total_steps,
        enabled_apis=enabled_apis,
        filter_downtime_days=filter_downtime_days,
        base_url=base_url,
        progress_logger=progress_logger,
        mp_workers=mp_workers,
    )
    
    return coordinator.get_relay_set() 