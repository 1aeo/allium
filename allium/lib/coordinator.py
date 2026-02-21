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
    fetch_collector_descriptors,
    get_worker_status, get_all_worker_status
)
from .relays import Relays
from .progress import log_progress
from .progress_logger import ProgressLogger
from .error_handlers import handle_worker_errors, handle_calculation_errors


class Coordinator:
    """
    Coordinator for managing API workers with threading support.
    Orchestrates parallel API fetching and relay set creation.
    
    Accepts either an argparse namespace (args) or individual keyword arguments
    for backward compatibility with tests.
    """
    
    def __init__(self, args=None, progress_logger=None, **kwargs):
        # Support both args namespace and keyword arguments (for tests/backward compat)
        if args is not None:
            # Read from argparse namespace
            self.output_dir = args.output_dir
            self.onionoo_details_url = args.onionoo_details_url
            self.onionoo_uptime_url = args.onionoo_uptime_url
            self.onionoo_bandwidth_url = args.onionoo_bandwidth_url
            self.aroi_url = args.aroi_url
            self.bandwidth_cache_hours = args.bandwidth_cache_hours
            self.use_bits = args.bandwidth_units == 'bits' if hasattr(args, 'bandwidth_units') else kwargs.get('use_bits', False)
            self.progress = args.progress
            self.enabled_apis = args.enabled_apis
            self.filter_downtime_days = args.filter_downtime_days
            self.base_url = args.base_url
            self.mp_workers = args.mp_workers
        else:
            # Backward-compatible keyword arguments (used by tests)
            self.output_dir = kwargs.get('output_dir', './www')
            self.onionoo_details_url = kwargs.get('onionoo_details_url', 'https://onionoo.torproject.org/details')
            self.onionoo_uptime_url = kwargs.get('onionoo_uptime_url', 'https://onionoo.torproject.org/uptime')
            self.onionoo_bandwidth_url = kwargs.get('onionoo_bandwidth_url', 'https://onionoo.torproject.org/bandwidth')
            self.aroi_url = kwargs.get('aroi_url', 'https://aroivalidator.1aeo.com/latest.json')
            self.bandwidth_cache_hours = kwargs.get('bandwidth_cache_hours', 12)
            self.use_bits = kwargs.get('use_bits', False)
            self.progress = kwargs.get('progress', False)
            self.enabled_apis = kwargs.get('enabled_apis', 'all')
            self.filter_downtime_days = kwargs.get('filter_downtime_days', 7)
            self.base_url = kwargs.get('base_url', '')
            self.mp_workers = kwargs.get('mp_workers', 4)
        
        self.start_time = kwargs.get('start_time') or (getattr(args, '_start_time', None) if args else None) or time.time()
        self.progress_step = kwargs.get('progress_step', 0)
        self.total_steps = kwargs.get('total_steps', 53)
        
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
        
        # Build API workers list from declarative registry
        # To add a new API: add one entry to API_WORKER_REGISTRY below
        self.api_workers = self._build_api_workers()
    
    # =========================================================================
    # API WORKER REGISTRY
    # =========================================================================
    # Declarative list of API workers. Each entry defines:
    #   name:       Internal identifier for the API
    #   fetch_fn:   Function to call (from workers.py)
    #   group:      Which --apis mode includes this worker ('details' or 'all')
    #   args_fn:    Lambda returning the argument list for fetch_fn
    #   enabled_fn: Optional callable returning bool (for feature flags)
    #
    # To add a new API source:
    #   1. Create a fetch function in workers.py
    #   2. Add one entry here
    #   3. Handle the data in Relays.enrich_with_api_data()
    # =========================================================================
    API_WORKER_REGISTRY = [
        {
            "name": "onionoo_details",
            "fetch_fn": fetch_onionoo_details,
            "group": "details",  # Included in both 'details' and 'all' modes
            "args_fn": lambda self: [self.onionoo_details_url, self._log_progress],
        },
        {
            "name": "onionoo_uptime",
            "fetch_fn": fetch_onionoo_uptime,
            "group": "all",
            "args_fn": lambda self: [self.onionoo_uptime_url, self._log_progress],
        },
        {
            "name": "onionoo_bandwidth",
            "fetch_fn": fetch_onionoo_bandwidth,
            "group": "all",
            "args_fn": lambda self: [self.onionoo_bandwidth_url, self.bandwidth_cache_hours, self._log_progress],
        },
        {
            "name": "aroi_validation",
            "fetch_fn": fetch_aroi_validation,
            "group": "all",
            "args_fn": lambda self: [self.aroi_url, self._log_progress],
        },
        {
            "name": "collector_consensus",
            "fetch_fn": fetch_collector_consensus_data,
            "group": "all",
            "args_fn": lambda self: [None, self._log_progress],
            "enabled_fn": None,  # Checked dynamically in _build_api_workers
        },
        {
            "name": "collector_descriptors",
            "fetch_fn": fetch_collector_descriptors,
            "group": "all",
            "args_fn": lambda self: [self._log_progress],
            "enabled_fn": None,  # Checked dynamically in _build_api_workers
        },
    ]
    
    def _build_api_workers(self):
        """Build the list of API workers based on enabled_apis mode and feature flags."""
        from .consensus import is_consensus_evaluation_enabled
        
        # Feature flag checks by worker name (avoids import issues in class-level lambdas)
        feature_flags = {
            "collector_consensus": is_consensus_evaluation_enabled,
            "collector_descriptors": is_consensus_evaluation_enabled,
        }
        
        workers = []
        for entry in self.API_WORKER_REGISTRY:
            # Include if group matches: 'details' workers run in all modes,
            # 'all' workers only run when --apis=all
            group = entry["group"]
            if group == "details" or self.enabled_apis == "all":
                # Check feature flag if present
                flag_fn = feature_flags.get(entry["name"])
                if flag_fn and not flag_fn():
                    continue
                workers.append((
                    entry["name"],
                    entry["fetch_fn"],
                    entry["args_fn"](self),
                ))
        return workers
        
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
        elif api_name == "collector_descriptors":
            return "CollecTor Descriptors API"
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

    def get_collector_descriptors_data(self):
        """
        Get CollecTor server descriptors summary if available.
        Contains family-cert fingerprints for Happy Family migration tracking.
        """
        return self.worker_data.get('collector_descriptors')

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
            collector_descriptors_data=self.get_collector_descriptors_data(),
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


def create_relay_set_with_coordinator(args, progress_logger=None):
    """
    Create a relay set using the coordinator system.
    
    Args:
        args: argparse namespace with all CLI arguments
        progress_logger: Optional ProgressLogger instance for consistent progress tracking
    """
    coordinator = Coordinator(args=args, progress_logger=progress_logger)
    return coordinator.get_relay_set()