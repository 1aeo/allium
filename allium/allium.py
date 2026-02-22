#!/usr/bin/env python3

"""
File: allium.py (executable)

Generate complete set of relay HTML pages and copy static files to the
output_dir

Default output directory: ./www
"""

import argparse
import os
import sys
import time
from lib.coordinator import create_relay_set_with_coordinator
from lib.progress_logger import create_progress_logger
from lib.site_generator import generate_site

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
    parser.add_argument(
        "--workers",
        dest="mp_workers",
        type=int,
        default=max(4, os.cpu_count() or 4),
        help="parallel workers for page generation (default: auto-detected CPU count, min 4)",
        required=False,
    )
    args = parser.parse_args()

    start_time = time.time()
    
    # Progress step breakdown (total: 53 steps):
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Setup (4 steps):
    #   1. Starting allium
    #   2. Creating output directory
    #   3. Output directory ready
    #   4. Initializing relay data
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Coordinator - API Fetching (16 steps, FIXED count):
    #   - Section start (1)
    #   - Starting threaded API fetching (1)
    #   - 6 API workers start messages (6) - details, uptime, bandwidth, aroi, collector, descriptors
    #   - 6 API workers complete messages (6)
    #   - All workers completed (1)
    #   - Section end (1)
    #   Note: Intermediate messages (cache status, parsing, etc.) are logged
    #   but don't increment the counter, making total predictable.
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Coordinator - Data Processing (4 steps):
    #   - Section start (1)
    #   - Creating relay set (1) - internal messages don't increment
    #   - Relay set created (1)
    #   - Section end (1)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Page Generation (31 steps):
    #   - Details API data loaded (1)
    #   - Section start (1)
    #   - Index page (generating + generated) x2
    #   - Top 500 page x2
    #   - All relays page x2
    #   - AROI leaderboards page x2
    #   - Network health dashboard x2
    #   - Miscellaneous sorted pages x2
    #   - Directory authorities x2
    #   - 7 key type pages complete (family, contact, as, country, flag, platform, first_seen)
    #   - Individual relay pages x2
    #   - Static files x2
    #   - Search index x2
    #   - Section end (1)
    #   - Completion message (1)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    setup_steps = 4
    coordinator_steps = 20  # API Fetching (16) + Data Processing (4)
    page_generation_steps = 31  # Page generation and completion
    total_steps = setup_steps + coordinator_steps + page_generation_steps  # 55 total steps

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
        RELAY_SET = create_relay_set_with_coordinator(args, progress_logger=progress_logger)
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
    
    # Generate the complete static site
    # Page definitions and generation logic are in lib/site_generator.py
    generate_site(RELAY_SET, args, progress_logger)
