"""
File: coordinator.py

Simple coordinator for managing API workers and coordinating with main allium logic.
Phase 1 implementation: basic threading coordination between workers and the main allium logic.
Phase 2 implementation: multiple API support, threading, and incremental rendering.
"""

import threading
from .relays import Relays
from .progress_logger import ProgressLogger
from .first_seen_correction import correct_first_seen


class Coordinator:
    """
    Coordinator for managing API workers with threading support.
    Orchestrates parallel API fetching and relay set creation.
    
    Accepts either an argparse namespace (args) or individual keyword arguments
    for backward compatibility with tests.
    """
    
    # Configuration attributes and their defaults - single source of truth
    # for both construction paths (argparse namespace and keyword arguments).
    _CONFIG_DEFAULTS = {
        'output_dir': './www',
        'onionoo_details_url': 'https://onionoo.torproject.org/details',
        'onionoo_uptime_url': 'https://onionoo.torproject.org/uptime',
        'onionoo_bandwidth_url': 'https://onionoo.torproject.org/bandwidth',
        'aroi_url': 'https://aroivalidator.1aeo.com/latest.json',
        'exit_dns_health_url': 'https://exitdnshealth.1aeo.com/latest.json',
        'bandwidth_cache_hours': 12,
        'progress': False,
        'enabled_apis': 'all',
        'filter_downtime_days': 7,
        'base_url': '',
        'mp_workers': 4,
    }

    def __init__(self, args=None, progress_logger=None, **kwargs):
        # Support both args namespace and keyword arguments (for tests/backward compat)
        for name, default in self._CONFIG_DEFAULTS.items():
            if args is not None:
                setattr(self, name, getattr(args, name, default))
            else:
                setattr(self, name, kwargs.get(name, default))
        # use_bits derives from args.bandwidth_units ('bits'|'bytes') when
        # provided; tests pass use_bits directly as a kwarg.
        if args is not None and hasattr(args, 'bandwidth_units'):
            self.use_bits = args.bandwidth_units == 'bits'
        else:
            self.use_bits = kwargs.get('use_bits', False)
        
        # ONE ProgressLogger instance is threaded through the whole pipeline
        # (allium.py → coordinator → relays → page_writer). Use the injected
        # instance when provided; otherwise create one (tests / direct use).
        if progress_logger is None:
            start_time = kwargs.get('start_time') or (getattr(args, '_start_time', None) if args else None)
            progress_logger = ProgressLogger(start_time, progress_enabled=self.progress)
        self.progress_logger = progress_logger
        self.start_time = progress_logger.start_time
        
        # Worker management
        self.worker_data = {}
        self.worker_threads = []
        
        # Build API workers list from declarative registry
        # To add a new API: add one entry to API_WORKER_REGISTRY below
        self.api_workers = self._build_api_workers()
    
    # =========================================================================
    # API WORKER REGISTRY
    # =========================================================================
    # Derived from workers.API_CONFIGS - the single source of truth. To add a
    # new API source: create a fetch function + APIConfig entry in workers.py
    # and handle the data in Relays.enrich_with_api_data(). The progress step
    # count (allium.py) follows automatically.
    # =========================================================================
    # The last element in each args_fn list is a progress logger placeholder.
    # _run_worker() replaces it with an API-specific logger before calling the
    # worker function. We use a no-op callable so the placeholder is safe to
    # call if _run_worker replacement is ever skipped (e.g., in tests).
    _noop_logger = staticmethod(lambda *args, **kwargs: None)

    @staticmethod
    def iter_enabled_worker_entries(enabled_apis):
        """Yield APIConfig entries enabled for this run.

        Single source of truth for worker gating - used by
        _build_api_workers AND by allium.py's total_steps derivation, so
        the progress step count follows the registry automatically.
        """
        from .consensus import is_consensus_evaluation_enabled
        from .workers import API_CONFIGS

        feature_flags = {
            "consensus_evaluation": is_consensus_evaluation_enabled,
        }

        for config in API_CONFIGS:
            if not config.enabled:
                continue
            # 'details' workers run in all modes, 'all' workers only when
            # --apis=all
            if config.group != "details" and enabled_apis != "all":
                continue
            flag_fn = feature_flags.get(config.feature_flag)
            if flag_fn and not flag_fn():
                continue
            yield config

    def _build_api_workers(self):
        """Build the list of API workers based on enabled_apis mode and feature flags."""
        return [
            (config.api_name, config.worker_fn, config.args_fn(self))
            for config in self.iter_enabled_worker_entries(self.enabled_apis)
        ]
        
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
            self.progress_logger.log(f"{api_display_name} - fetching data...")
            
            result = worker_func(*args_with_api_logger)
            self.worker_data[api_name] = result
            if result is not None:
                self.progress_logger.log(f"{api_display_name} - completed successfully")
            else:
                self.progress_logger.log(f"{api_display_name} - warning: returned no data")
        except Exception as e:
            # Use centralized error handling approach
            api_display_name = self._get_api_display_name(api_name)
            self.progress_logger.log(f"{api_display_name} - error: {str(e)}")
            self.worker_data[api_name] = None
            
            # CI debugging with centralized approach
            import os
            if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
                print(f"🔧 CI Debug: {api_name} worker failed with: {e}")
                import traceback
                traceback.print_exc()

    def _get_api_display_name(self, api_name):
        """Get progress display name for API (from the registry configs)"""
        from .workers import API_CONFIGS
        for config in API_CONFIGS:
            if config.api_name == api_name and config.progress_name:
                return config.progress_name
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
            self.progress_logger.log_without_increment(f"{api_display_name} - {message}")

        return api_logger

    def fetch_all_apis_threaded(self):
        """
        Fetch data from all APIs using threading (Phase 2 implementation)
        """
        if self.progress:
            self.progress_logger.start_section("API Fetching")
            self.progress_logger.log("Starting threaded API fetching...")
        
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
            self.progress_logger.log("All API workers completed")
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
                self.progress_logger.log(f"Error during threaded API fetching: {e}")
            print(f"❌ Error: Failed to fetch API data: {e}")
            print("🔧 This might be due to network connectivity issues")
            return None
        
        # Return the details data for backward compatibility
        details_data = all_data.get('onionoo_details')
        if details_data:
            return details_data
        else:
            if self.progress:
                self.progress_logger.log("Failed to fetch onionoo details data")
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

    def create_relay_set(self, relay_data):
        """
        Create Relays instance with fetched data.
        
        The heavy lifting is split between Relays.__init__ (core processing from
        details API) and Relays.enrich_with_api_data() (secondary API enrichment).
        See enrich_with_api_data() docstring for the full pipeline overview.
        """
        if self.progress:
            self.progress_logger.start_section("Data Processing")
            self.progress_logger.log("Creating relay set with Details API data...")

        # Workaround for onionoo's mass `first_seen` reset bug (upstream
        # issues #40018/#40028/#40033/#40042). Repair relay['first_seen']
        # from /uptime history BEFORE the Relays constructor runs, so
        # categorisation, leaderboards, intelligence engine, templates,
        # and search index all see the corrected value with no rework.
        # Applies no corrections if uptime data is unavailable (e.g.
        # --apis details); still emits a summary log line in progress mode.
        # See allium/lib/first_seen_correction.py for full background.
        correct_first_seen(
            relay_data,
            self.get_uptime_data(),
            progress_logger=self.progress_logger if self.progress else None,
        )

        relay_set = Relays(
            output_dir=self.output_dir,
            onionoo_url=self.onionoo_details_url,
            relay_data=relay_data,
            use_bits=self.use_bits,
            progress=self.progress,
            filter_downtime_days=self.filter_downtime_days,
            base_url=self.base_url,
            progress_logger=self.progress_logger,
            mp_workers=self.mp_workers,
        )
        
        if relay_set.json is None:
            if self.progress:
                self.progress_logger.log("Failed to create relay set")
            return None

        # Surface first_seen correction stats for diagnostics (api_diagnostics,
        # tests, future telemetry). Safe to access -- always stamped by
        # correct_first_seen, even when no correction was applied.
        relay_set.first_seen_repair_stats = relay_data.get(
            '_first_seen_correction_summary'
        )

        # Enrich with secondary API data (uptime, bandwidth, AROI, collector)
        # Processing order and dependencies are documented in enrich_with_api_data()
        relay_set.enrich_with_api_data(
            uptime_data=self.get_uptime_data(),
            bandwidth_data=self.worker_data.get('onionoo_bandwidth'),
            aroi_validation_data=self.worker_data.get('aroi_validation'),
            exit_dns_health_data=self.worker_data.get('exit_dns_health'),
            collector_consensus_data=self.worker_data.get('collector_consensus'),
            consensus_health_data=self.worker_data.get('consensus_health'),
            collector_descriptors_data=self.worker_data.get('collector_descriptors'),
        )

        if self.progress:
            self.progress_logger.log("Relay set created successfully with Details API and Uptime API data")
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
        relay_set = self.create_relay_set(relay_data)

        # Probe authority latency here (not during page rendering) so page
        # generation is pure rendering; misc-authorities consumes the result
        if relay_set is not None:
            from .page_writer import probe_authority_latency
            try:
                relay_set.authority_latency_status = probe_authority_latency(relay_set)
            except Exception as e:
                # Non-fatal: rendering falls back to its inline probe path
                self.progress_logger.log_without_increment(
                    f"authority latency probe failed: {e}")

        return relay_set


def create_relay_set_with_coordinator(args, progress_logger=None):
    """
    Create a relay set using the coordinator system.
    
    Args:
        args: argparse namespace with all CLI arguments
        progress_logger: Optional ProgressLogger instance for consistent progress tracking
    """
    coordinator = Coordinator(args=args, progress_logger=progress_logger)
    return coordinator.get_relay_set()