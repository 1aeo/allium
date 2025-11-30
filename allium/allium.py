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
from typing import Any, Dict, Optional
from lib.relays import Relays
from lib.coordinator import create_relay_set_with_coordinator
from lib.progress import log_progress
from lib.progress_logger import create_progress_logger
from lib.page_context import get_page_context, get_misc_page_context, StandardTemplateContexts

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
        print("💡 Install it with: pip3 install -r config/requirements.txt")
        sys.exit(1)
    
    # Check Python version
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
        "--base-url",
        dest="base_url",
        type=str,
        default="",
        help='base URL for vanity URLs (default: "" for root-relative paths like /domain/)',
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
        "--onionoo-bandwidth-url",
        dest="onionoo_bandwidth_url",
        type=str,
        default="https://onionoo.torproject.org/bandwidth",
        help=(
            "onionoo historical bandwidth API HTTP URL (default "
            '"https://onionoo.torproject.org/bandwidth")'
        ),
        required=False,
    )
    parser.add_argument(
        "--aroi-url",
        dest="aroi_url",
        type=str,
        default="https://aroivalidator.1aeo.com/latest.json",
        help=(
            "AROI validator API HTTP URL (default "
            '"https://aroivalidator.1aeo.com/latest.json")'
        ),
        required=False,
    )
    parser.add_argument(
        "--bandwidth-cache-hours",
        dest="bandwidth_cache_hours",
        type=int,
        default=12,
        help="hours to cache historical bandwidth data before refreshing (default: 12)",
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
    parser.add_argument(
        "--filter-downtime",
        dest="filter_downtime_days",
        type=int,
        default=7,
        help="filter out relays offline for more than N days (default: 7, use 0 to disable)",
        required=False,
    )
    args = parser.parse_args()

    start_time = time.time()
    # Updated to account for all actual progress steps:
    # Setup steps (1-4): starting, output dir creation, ready, initializing
    # API steps (5-18): threaded fetching, both APIs (fetch->parse->cache->success->complete), relay set creation
    # Site generation steps (19-35): data loaded, index, top500, all relays, AROI, misc pages, unique values, relay info, static files, completion
    setup_steps = 4
    api_steps = 26  # API-related steps with parallel fetching (Details, Uptime, Bandwidth, AROI validation with detailed logging)
    site_generation_steps = 19  # Site generation and completion steps (includes relay set processing, page generation)
    total_steps = setup_steps + api_steps + site_generation_steps  # 49 total steps

    # Create unified progress logger
    progress_logger = create_progress_logger(start_time, 0, total_steps, args.progress)

    if args.progress:
        print(f"🌐 Allium - Tor Relay Analytics Generator")
        print(f"========================================")
        check_dependencies(show_progress=True)
    else:
        check_dependencies(show_progress=False)
    
    progress_logger.log("Starting allium static site generation...")

    # Fail fast - ensure output directory exists before expensive processing
    progress_logger.log("Creating output directory...")
    ensure_output_directory(args.output_dir)
    progress_logger.log(f"Output directory ready at {args.output_dir}")

    # object containing onionoo data and processing routines
    progress_logger.log("Initializing relay data from onionoo (using coordinator)...")
    
    try:
        RELAY_SET = create_relay_set_with_coordinator(args.output_dir, args.onionoo_details_url, args.onionoo_uptime_url, args.onionoo_bandwidth_url, args.aroi_url, args.bandwidth_cache_hours, args.bandwidth_units == 'bits', args.progress, start_time, progress_logger.get_current_step(), total_steps, args.enabled_apis, args.filter_downtime_days, args.base_url)
        if RELAY_SET is None or RELAY_SET.json == None:
            # Progress-style error context message (conditional on progress flag)
            progress_logger.log("No onionoo data available, exiting gracefully")
            # Error messages always shown (not conditional)
            print("⚠️  No onionoo data available - this might be due to network issues or the service being temporarily unavailable")
            print("🔧 In CI environments, this is often a temporary issue that resolves on retry")
            sys.exit(0)
    except Exception as e:
        # Progress-style error context message (conditional on progress flag)
        progress_logger.log(f"Failed to initialize relay data: {e}")
        # Error messages always shown (not conditional)
        print(f"❌ Error: Failed to initialize relay data: {e}")
        print("🔧 In CI environments, this might be due to network connectivity or temporary service issues")
        print("💡 Try running the command again, or check your internet connection")
        sys.exit(1)
    
    # Update progress_step from the RELAY_SET object (it was incremented during API processing and intelligence analysis)
    progress_logger.set_step(RELAY_SET.progress_step)
    progress_logger.log(f"Details API data loaded successfully - found {len(RELAY_SET.json.get('relays', []))} relays")

    # Output directory already created early via ensure_output_directory() - skip redundant creation

    # AROI leaderboards as main index page, preserve top 500 relays at separate path
    progress_logger.log("Generating index page (AROI leaderboards)...")
    page_ctx = get_page_context('index', 'home')
    RELAY_SET.write_misc(
        template="aroi-leaderboards.html",
        path="index.html",
        page_ctx=page_ctx,
    )
    progress_logger.log("Generated index page with AROI leaderboards")

    # Preserve top 500 relays at dedicated path
    progress_logger.log("Generating top 500 relays page...")
    RELAY_SET.write_misc(
        template="index.html",
        path="top500.html",
        page_ctx=page_ctx,
        is_index=True,
    )
    progress_logger.log("Generated top 500 relays page")

    progress_logger.log("Generating all relays page...")
    page_ctx = get_misc_page_context('All Relays')
    RELAY_SET.write_misc(template="all.html", path="misc/all.html", page_ctx=page_ctx)
    progress_logger.log("Generated all relays page")

    # AROI leaderboards page
    progress_logger.log("Generating AROI leaderboards page...")
    aroi_ctx = get_misc_page_context('AROI Champions Dashboard')
    RELAY_SET.write_misc(template="aroi-leaderboards.html", path="misc/aroi-leaderboards.html", page_ctx=aroi_ctx)
    progress_logger.log("Generated AROI leaderboards page")

    # Network Health Dashboard page
    progress_logger.log("Generating network health dashboard...")
    standard_contexts = StandardTemplateContexts(RELAY_SET)
    health_ctx = standard_contexts.get_index_page_context('Network Health Dashboard', RELAY_SET.timestamp)
    RELAY_SET.write_misc(template="network-health-dashboard.html", path="network-health.html", page_ctx=health_ctx)
    progress_logger.log("Generated network health dashboard")

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
    progress_logger.log("Generating miscellaneous sorted pages...")
    
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
            standard_contexts = StandardTemplateContexts(RELAY_SET)
            page_ctx = standard_contexts.get_misc_page_context(f"misc-{page_type}.html", page_title, sorted_by=v)
            RELAY_SET.write_misc(
                template=f"misc-{page_type}.html",
                path=f"misc/{page_type}-{k}.html",
                sorted_by=v,
                page_ctx=page_ctx,
            )

    progress_logger.log("Generated 6 miscellaneous sorted pages")

    # directory authorities page  
    progress_logger.log("Generating directory authorities monitoring page...")
    authorities_ctx = get_misc_page_context('Directory Authorities')
    RELAY_SET.write_misc(
        template="misc-authorities.html",
        path="misc/authorities.html",
        page_ctx=authorities_ctx,
    )
    progress_logger.log("Generated directory authorities monitoring page")
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

    progress_logger.log("Generating pages by unique values...")
    for i, k in enumerate(keys):
        RELAY_SET.write_pages_by_key(k)
    progress_logger.log(f"Generated pages for {len(keys)} unique value types")

    # per-relay info pages
    progress_logger.log("Generating individual relay info pages...")
    RELAY_SET.write_relay_info()
    progress_logger.log(f"Generated individual pages for {len(RELAY_SET.json.get('relays', []))} relays")

    # copy static directory and its contents if it doesn't exist
    progress_logger.log("Copying static files...")
    if not os.path.exists(os.path.join(args.output_dir, "static")):
        copytree(
            os.path.join(ABS_PATH, "static"),
            os.path.join(args.output_dir, "static"),
        )
        progress_logger.log("Copied static files to output directory")
    else:
        progress_logger.log("Static files already exist, skipping copy")

    progress_logger.log("Allium static site generation completed successfully!")
