#!/usr/bin/env python3

"""
File: allium.py (executable)

Generate complete set of relay HTML pages and copy static files to the
output_dir

Default output directory: ./www
"""

import argparse
import os
import resource
import sys
import time
from shutil import copytree
from lib.relays import Relays
from lib.coordinator import create_relay_set_with_coordinator
from lib.progress import log_progress

ABS_PATH = os.path.dirname(os.path.abspath(__file__))



def ensure_output_directory(output_dir):
    """
    Create output directory and verify write permissions.
    Fails fast with clear error messages before expensive processing begins.
    
    Args:
        output_dir (str): Path to the output directory to create
        
    Raises:
        SystemExit: If directory creation fails or permissions are insufficient
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
    except PermissionError as e:
        print(f"❌ Error: Permission denied creating output directory '{output_dir}'")
        print(f"💡 Try running with a different output directory:")
        print(f"   python3 allium.py --out ~/allium-output --progress")
        print(f"📋 Or fix permissions: chmod 755 {os.path.dirname(output_dir)}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: Failed to create output directory '{output_dir}': {e}")
        print(f"💡 Make sure the parent directory exists and you have write permissions")
        sys.exit(1)

def get_page_context(page_type, breadcrumb_type=None, breadcrumb_data=None):
    """Get page context with path_prefix and breadcrumb info for different page types"""
    contexts = {
        'index': {'path_prefix': './'},
        'misc': {'path_prefix': '../'},
        'detail': {'path_prefix': '../../'}
    }
    ctx = contexts.get(page_type, contexts['misc']).copy()
    
    # Add breadcrumb information if provided
    if breadcrumb_type:
        ctx['breadcrumb_type'] = breadcrumb_type
        ctx['breadcrumb_data'] = breadcrumb_data or {}
    
    return ctx

def get_misc_page_context(page_name):
    """Helper function for creating misc page contexts with consistent structure"""
    return get_page_context('misc', 'misc_listing', {'page_name': page_name})

def check_dependencies(show_progress=False):
    """Check if required dependencies are available."""
    try:
        import jinja2
        if show_progress:
            if hasattr(jinja2, '__version__'):
                version = jinja2.__version__
                print(f"✅ Jinja2 {version} found")
            else:
                print("✅ Jinja2 found")
    except ImportError:
        print("❌ Error: Jinja2 not found")
        print("💡 Install it with: pip3 install -r requirements.txt")
        sys.exit(1)
    
    # Check Python version
    import sys
    if sys.version_info < (3, 8):
        print(f"❌ Error: Python 3.8+ required, found {sys.version}")
        print("💡 Please upgrade Python or use a virtual environment with Python 3.8+")
        sys.exit(1)

def log_step_progress(message, start_time, progress_step, total_steps, progress_enabled, increment=True):
    """
    Helper function to log progress and optionally increment step counter.
    
    Args:
        message: Progress message
        start_time: Start time for elapsed calculation  
        progress_step: Current progress step (passed by reference via list/dict)
        total_steps: Total number of steps
        progress_enabled: Whether progress logging is enabled
        increment: Whether to increment the step counter
        
    Returns:
        Updated progress_step value
    """
    if increment:
        progress_step += 1
    log_progress(message, start_time, progress_step, total_steps, progress_enabled)
    return progress_step

if __name__ == "__main__":
    desc = "allium: generate static tor relay metrics and statistics"
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        "--out",
        dest="output_dir",
        type=str,
        default="./www",
        help='directory to store rendered files (default "./www")',
        required=False,
    )
    parser.add_argument(
        "--display-bandwidth-units",
        dest="bandwidth_units",
        choices=['bits', 'bytes'],
        default='bits',
        help="display bandwidth in bits/second (Kbit/s, Mbit/s, Gbit/s) or bytes/second (KB/s, MB/s, GB/s). Default: bits",
    )
    parser.add_argument(
        "-p", "--progress",
        dest="progress",
        action="store_true",
        help="show progress updates during execution",
        required=False,
    )
    parser.add_argument(
        "--onionoo-details-url",
        dest="onionoo_details_url",
        type=str,
        default="https://onionoo.torproject.org/details",
        help=(
            "onionoo details API HTTP URL (default "
            '"https://onionoo.torproject.org/details")'
        ),
        required=False,
    )
    parser.add_argument(
        "--onionoo-uptime-url",
        dest="onionoo_uptime_url",
        type=str,
        default="https://onionoo.torproject.org/uptime",
        help=(
            "onionoo uptime API HTTP URL (default "
            '"https://onionoo.torproject.org/uptime")'
        ),
        required=False,
    )
    parser.add_argument(
        "--apis",
        dest="enabled_apis",
        type=str,
        choices=['details', 'all'],
        default='all',
        help=(
            "select which APIs to enable: "
            "details (~400MB memory, details API only), "
            "all (~2.4GB memory, details + uptime APIs). "
            "Default: all"
        ),
        required=False,
    )
    args = parser.parse_args()

    start_time = time.time()
    progress_step = 0
    # Updated to account for all actual progress steps:
    # Setup steps (1-4): starting, output dir creation, ready, initializing
    # API steps (5-18): threaded fetching, both APIs (fetch->parse->cache->success->complete), relay set creation
    # Site generation steps (19-35): data loaded, index, top500, all relays, AROI, misc pages, unique values, relay info, static files, completion
    setup_steps = 4
    api_steps = 14  # Maximum API-related steps (when all APIs enabled) 
    site_generation_steps = 17  # Site generation and completion steps (added top500 page)
    total_steps = setup_steps + api_steps + site_generation_steps  # 35 total steps

    if args.progress:
        print(f"🌐 Allium - Tor Relay Analytics Generator")
        print(f"========================================")
        check_dependencies(show_progress=True)
    else:
        check_dependencies(show_progress=False)
    
    progress_step = log_step_progress("Starting allium static site generation...", start_time, progress_step, total_steps, args.progress)

    # Fail fast - ensure output directory exists before expensive processing
    progress_step = log_step_progress("Creating output directory...", start_time, progress_step, total_steps, args.progress)
    ensure_output_directory(args.output_dir)
    progress_step = log_step_progress(f"Output directory ready at {args.output_dir}", start_time, progress_step, total_steps, args.progress)

    # object containing onionoo data and processing routines
    progress_step = log_step_progress("Initializing relay data from onionoo (using coordinator)...", start_time, progress_step, total_steps, args.progress)
    
    try:
        RELAY_SET = create_relay_set_with_coordinator(args.output_dir, args.onionoo_details_url, args.onionoo_uptime_url, args.bandwidth_units == 'bits', args.progress, start_time, progress_step, total_steps, args.enabled_apis)
        if RELAY_SET is None or RELAY_SET.json == None:
            # Progress-style error context message (conditional on progress flag)
            progress_step = log_step_progress("No onionoo data available, exiting gracefully", start_time, progress_step, total_steps, args.progress)
            # Error messages always shown (not conditional)
            print("⚠️  No onionoo data available - this might be due to network issues or the service being temporarily unavailable")
            print("🔧 In CI environments, this is often a temporary issue that resolves on retry")
            sys.exit(0)
    except Exception as e:
        # Progress-style error context message (conditional on progress flag)
        progress_step = log_step_progress(f"Failed to initialize relay data: {e}", start_time, progress_step, total_steps, args.progress)
        # Error messages always shown (not conditional)
        print(f"❌ Error: Failed to initialize relay data: {e}")
        print("🔧 In CI environments, this might be due to network connectivity or temporary service issues")
        print("💡 Try running the command again, or check your internet connection")
        sys.exit(1)
    
    # Update progress_step from the RELAY_SET object (it was incremented during API processing and intelligence analysis)
    progress_step = RELAY_SET.progress_step
    progress_step = log_step_progress(f"Details API data loaded successfully - found {len(RELAY_SET.json.get('relays', []))} relays", start_time, progress_step, total_steps, args.progress)

    # Output directory already created early via ensure_output_directory() - skip redundant creation

    # AROI leaderboards as main index page, preserve top 500 relays at separate path
    progress_step = log_step_progress("Generating index page (AROI leaderboards)...", start_time, progress_step, total_steps, args.progress)
    page_ctx = get_page_context('index', 'home')
    RELAY_SET.write_misc(
        template="aroi-leaderboards.html",
        path="index.html",
        page_ctx=page_ctx,
    )
    progress_step = log_step_progress("Generated index page with AROI leaderboards", start_time, progress_step, total_steps, args.progress)

    # Preserve top 500 relays at dedicated path
    progress_step = log_step_progress("Generating top 500 relays page...", start_time, progress_step, total_steps, args.progress)
    RELAY_SET.write_misc(
        template="index.html",
        path="top500.html",
        page_ctx=page_ctx,
        is_index=True,
    )
    progress_step = log_step_progress("Generated top 500 relays page", start_time, progress_step, total_steps, args.progress)

    progress_step = log_step_progress("Generating all relays page...", start_time, progress_step, total_steps, args.progress)
    page_ctx = get_misc_page_context('All Relays')
    RELAY_SET.write_misc(template="all.html", path="misc/all.html", page_ctx=page_ctx)
    progress_step = log_step_progress("Generated all relays page", start_time, progress_step, total_steps, args.progress)

    # AROI leaderboards page
    progress_step = log_step_progress("Generating AROI leaderboards page...", start_time, progress_step, total_steps, args.progress)
    aroi_ctx = get_misc_page_context('AROI Champions Dashboard')
    RELAY_SET.write_misc(template="aroi-leaderboards.html", path="misc/aroi-leaderboards.html", page_ctx=aroi_ctx)
    progress_step = log_step_progress("Generated AROI leaderboards page", start_time, progress_step, total_steps, args.progress)

    # Network Health Dashboard page
    progress_step = log_step_progress("Generating network health dashboard...", start_time, progress_step, total_steps, args.progress)
    health_ctx = get_page_context('index', 'home', {'page_name': 'Network Health Dashboard'})
    # Add timestamp for the dashboard
    health_ctx['timestamp_str'] = RELAY_SET.timestamp
    RELAY_SET.write_misc(template="network-health-dashboard.html", path="network-health.html", page_ctx=health_ctx)
    progress_step = log_step_progress("Generated network health dashboard", start_time, progress_step, total_steps, args.progress)

    # miscellaneous page filename suffixes and sorted-by keys
    misc_pages = {
        "by-bandwidth": "1.bandwidth",
        "by-overall-bandwidth": "1.bandwidth",
        "by-guard-bandwidth": "1.guard_bandwidth",
        "by-middle-bandwidth": "1.middle_bandwidth", 
        "by-exit-bandwidth": "1.exit_bandwidth",
        "by-bandwidth-mean": "1.bandwidth_mean",
        "by-consensus-weight": "1.consensus_weight_fraction",
        "by-guard-consensus-weight": "1.guard_consensus_weight_fraction",
        "by-middle-consensus-weight": "1.middle_consensus_weight_fraction",
        "by-exit-consensus-weight": "1.exit_consensus_weight_fraction",
        "by-exit-count": "1.exit_count",
        "by-guard-count": "1.guard_count",
        "by-middle-count": "1.middle_count",
        "by-unique-as-count": "1.unique_as_count",
        "by-unique-contact-count": "1.unique_contact_count",
        "by-unique-family-count": "1.unique_family_count",
        "by-first-seen": "1.first_seen",
    }

    # miscellaneous-sorted (per misc_pages k/v) HTML pages
    progress_step = log_step_progress("Generating miscellaneous sorted pages...", start_time, progress_step, total_steps, args.progress)
    
    # Define page types for DRY generation
    misc_page_types = [
        ('families', 'Browse by Family'),
        ('networks', 'Browse by Network'), 
        ('contacts', 'Browse by Contact'),
        ('countries', 'Browse by Country'),
        ('platforms', 'Browse by Platform')
    ]
    
    for k, v in misc_pages.items():
        for page_type, page_title in misc_page_types:
            page_ctx = get_misc_page_context(page_title)
            RELAY_SET.write_misc(
                template=f"misc-{page_type}.html",
                path=f"misc/{page_type}-{k}.html",
                sorted_by=v,
                page_ctx=page_ctx,
            )

    progress_step = log_step_progress("Generated 6 miscellaneous sorted pages", start_time, progress_step, total_steps, args.progress)

    # directory authorities page  
    progress_step = log_step_progress("Generating directory authorities monitoring page...", start_time, progress_step, total_steps, args.progress)
    authorities_ctx = get_misc_page_context('Directory Authorities')
    RELAY_SET.write_misc(
        template="misc-authorities.html",
        path="misc/authorities.html",
        page_ctx=authorities_ctx,
    )
    progress_step = log_step_progress("Generated directory authorities monitoring page", start_time, progress_step, total_steps, args.progress)
    # onionoo keys used to generate pages by unique value; e.g. AS43350
    keys = [
        "as",
        "contact",
        "country",
        "family",
        "flag",
        "platform",
        "first_seen",
    ]

    progress_step = log_step_progress("Generating pages by unique values...", start_time, progress_step, total_steps, args.progress)
    for i, k in enumerate(keys):
        RELAY_SET.write_pages_by_key(k)
    progress_step = log_step_progress(f"Generated pages for {len(keys)} unique value types", start_time, progress_step, total_steps, args.progress)

    # per-relay info pages
    progress_step = log_step_progress("Generating individual relay info pages...", start_time, progress_step, total_steps, args.progress)
    RELAY_SET.write_relay_info()
    progress_step = log_step_progress(f"Generated individual pages for {len(RELAY_SET.json.get('relays', []))} relays", start_time, progress_step, total_steps, args.progress)

    # copy static directory and its contents if it doesn't exist
    progress_step = log_step_progress("Copying static files...", start_time, progress_step, total_steps, args.progress)
    if not os.path.exists(os.path.join(args.output_dir, "static")):
        copytree(
            os.path.join(ABS_PATH, "static"),
            os.path.join(args.output_dir, "static"),
        )
        progress_step = log_step_progress("Copied static files to output directory", start_time, progress_step, total_steps, args.progress)
    else:
        progress_step = log_step_progress("Static files already exist, skipping copy", start_time, progress_step, total_steps, args.progress)

    progress_step = log_step_progress("Allium static site generation completed successfully!", start_time, progress_step, total_steps, args.progress)
