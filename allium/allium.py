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

ABS_PATH = os.path.dirname(os.path.abspath(__file__))

def get_memory_usage():
    """
    Get current memory usage using Python's built-in resource module and /proc/self/status.
    Returns formatted string with current RSS (physical) and peak memory usage.
    
    Returns:
        str: Formatted memory usage string like "RSS: 45.2MB, Peak: 123.4MB"
    """
    try:
        # Get peak memory from resource module
        usage = resource.getrusage(resource.RUSAGE_SELF)
        peak_kb = usage.ru_maxrss
        if sys.platform == 'darwin':  # macOS reports in bytes
            peak_kb = peak_kb / 1024
        
        # Get current RSS from /proc/self/status (Linux specific)
        current_rss_kb = None
        try:
            with open('/proc/self/status', 'r') as f:
                for line in f:
                    if line.startswith('VmRSS:'):
                        # Extract RSS value in KB
                        current_rss_kb = int(line.split()[1])
                        break
        except (FileNotFoundError, PermissionError, ValueError):
            # Fall back to showing only peak if /proc/self/status is unavailable
            current_rss_kb = peak_kb
        
        # Format to MB with 1 decimal place
        current_mb = (current_rss_kb or peak_kb) / 1024
        peak_mb = peak_kb / 1024
        
        if current_rss_kb and current_rss_kb != peak_kb:
            return f"RSS: {current_mb:.1f}MB, Peak: {peak_mb:.1f}MB"
        else:
            # If current RSS unavailable or same as peak, just show peak
            return f"Peak RSS: {peak_mb:.1f}MB"
    except Exception as e:
        return f"Memory: unavailable ({e})"

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
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Starting allium static site generation...")
    else:
        check_dependencies(show_progress=False)

    # Fail fast - ensure output directory exists before expensive processing
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Creating output directory...")
    ensure_output_directory(args.output_dir)
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Output directory ready at {args.output_dir}")

    # object containing onionoo data and processing routines
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Initializing relay data from onionoo (using coordinator)...")
    
    try:
        RELAY_SET = create_relay_set_with_coordinator(args.output_dir, args.onionoo_details_url, args.onionoo_uptime_url, args.bandwidth_units == 'bits', args.progress, start_time, progress_step, total_steps, args.enabled_apis)
        if RELAY_SET is None or RELAY_SET.json == None:
            if args.progress:
                print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: No onionoo data available, exiting gracefully")
            print("⚠️  No onionoo data available - this might be due to network issues or the service being temporarily unavailable")
            print("🔧 In CI environments, this is often a temporary issue that resolves on retry")
            sys.exit(0)
    except Exception as e:
        if args.progress:
            print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Failed to initialize relay data: {e}")
        print(f"❌ Error: Failed to initialize relay data: {e}")
        print("🔧 In CI environments, this might be due to network connectivity or temporary service issues")
        print("💡 Try running the command again, or check your internet connection")
        sys.exit(1)
    
    # Update progress_step from the RELAY_SET object (it was incremented during API processing and intelligence analysis)
    progress_step = RELAY_SET.progress_step
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Details API data loaded successfully - found {len(RELAY_SET.json.get('relays', []))} relays")

    # Output directory already created early via ensure_output_directory() - skip redundant creation

    # AROI leaderboards as main index page, preserve top 500 relays at separate path
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generating index page (AROI leaderboards)...")
    page_ctx = get_page_context('index', 'home')
    RELAY_SET.write_misc(
        template="aroi-leaderboards.html",
        path="index.html",
        page_ctx=page_ctx,
    )
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generated index page with AROI leaderboards")

    # Preserve top 500 relays at dedicated path
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generating top 500 relays page...")
    RELAY_SET.write_misc(
        template="index.html",
        path="top500.html",
        page_ctx=page_ctx,
        is_index=True,
    )
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generated top 500 relays page")

    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generating all relays page...")
    page_ctx = get_page_context('misc', 'misc_listing', {'page_name': 'All Relays'})
    RELAY_SET.write_misc(template="all.html", path="misc/all.html", page_ctx=page_ctx)
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generated all relays page")

    # AROI leaderboards page
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generating AROI leaderboards page...")
    aroi_ctx = get_page_context('misc', 'misc_listing', {'page_name': 'AROI Champions Dashboard'})
    RELAY_SET.write_misc(template="aroi-leaderboards.html", path="misc/aroi-leaderboards.html", page_ctx=aroi_ctx)
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generated AROI leaderboards page")

    # Network Health Dashboard page
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generating network health dashboard...")
    health_ctx = get_page_context('index', 'home', {'page_name': 'Network Health Dashboard'})
    RELAY_SET.write_misc(template="network-health-dashboard.html", path="network-health.html", page_ctx=health_ctx)
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generated network health dashboard")

    # miscellaneous page filename suffixes and sorted-by keys
    misc_pages = {
        "by-bandwidth": "1.bandwidth",
        "by-overall-bandwidth": "1.bandwidth",
        "by-guard-bandwidth": "1.guard_bandwidth",
        "by-middle-bandwidth": "1.middle_bandwidth", 
        "by-exit-bandwidth": "1.exit_bandwidth",
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
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generating miscellaneous sorted pages...")
    for k, v in misc_pages.items():
        families_ctx = get_page_context('misc', 'misc_listing', {'page_name': 'Browse by Family'})
        RELAY_SET.write_misc(
            template="misc-families.html",
            path="misc/families-{}.html".format(k),
            sorted_by=v,
            page_ctx=families_ctx,
        )
        networks_ctx = get_page_context('misc', 'misc_listing', {'page_name': 'Browse by Network'})
        RELAY_SET.write_misc(
            template="misc-networks.html",
            path="misc/networks-{}.html".format(k),
            sorted_by=v,
            page_ctx=networks_ctx,
        )
        contacts_ctx = get_page_context('misc', 'misc_listing', {'page_name': 'Browse by Contact'})
        RELAY_SET.write_misc(
            template="misc-contacts.html",
            path="misc/contacts-{}.html".format(k),
            sorted_by=v,
            page_ctx=contacts_ctx,
        )
        countries_ctx = get_page_context('misc', 'misc_listing', {'page_name': 'Browse by Country'})
        RELAY_SET.write_misc(
            template="misc-countries.html",
            path="misc/countries-{}.html".format(k),
            sorted_by=v,
            page_ctx=countries_ctx,
        )
        platforms_ctx = get_page_context('misc', 'misc_listing', {'page_name': 'Browse by Platform'})
        RELAY_SET.write_misc(
            template="misc-platforms.html",
            path="misc/platforms-{}.html".format(k),
            sorted_by=v,
            page_ctx=platforms_ctx,
        )

    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generated 6 miscellaneous sorted pages")
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

    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generating pages by unique values...")
    for i, k in enumerate(keys):
        RELAY_SET.write_pages_by_key(k)
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generated pages for {len(keys)} unique value types")

    # per-relay info pages
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generating individual relay info pages...")
    RELAY_SET.write_relay_info()
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generated individual pages for {len(RELAY_SET.json.get('relays', []))} relays")

    # copy static directory and its contents if it doesn't exist
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Copying static files...")
    if not os.path.exists(os.path.join(args.output_dir, "static")):
        copytree(
            os.path.join(ABS_PATH, "static"),
            os.path.join(args.output_dir, "static"),
        )
        if args.progress:
            print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Copied static files to output directory")
    else:
        if args.progress:
            print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Static files already exist, skipping copy")

    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Allium static site generation completed successfully!")
