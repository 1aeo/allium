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
        print(f"Error: Permission denied creating output directory '{output_dir}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to create output directory '{output_dir}': {e}")
        sys.exit(1)

def get_page_context(page_type):
    """Get page context with path_prefix for different page types"""
    contexts = {
        'index': {'path_prefix': './'},
        'misc': {'path_prefix': '../'},
        'detail': {'path_prefix': '../../'}
    }
    return contexts.get(page_type, contexts['misc'])

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
        "--onionoo-url",
        dest="onionoo_url",
        type=str,
        default="https://onionoo.torproject.org/details",
        help=(
            "onionoo HTTP URL (default "
            '"https://onionoo.torproject.org/details")'
        ),
        required=False,
    )
    args = parser.parse_args()

    start_time = time.time()
    progress_step = 0
    total_steps = 18

    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Starting allium static site generation...")

    # Fail fast - ensure output directory exists before expensive processing
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Creating output directory...")
    ensure_output_directory(args.output_dir)
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Output directory ready at {args.output_dir}")

    # object containing onionoo data and processing routines
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Initializing relay data from onionoo...")
    RELAY_SET = Relays(args.output_dir, args.onionoo_url, args.bandwidth_units == 'bits')
    if RELAY_SET.json == None:
        sys.exit(0)
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Loaded relay data from onionoo - found {len(RELAY_SET.json.get('relays', []))} relays")

    # Output directory already created early via ensure_output_directory() - skip redundant creation

    # index and "all" HTML relay sets; index set limited to 500 relays
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generating index page...")
    page_ctx = get_page_context('index')
    RELAY_SET.write_misc(
        template="index.html",
        path="index.html",
        page_ctx=page_ctx,
        is_index=True,
    )
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generated index page with top 500 relays")

    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generating all relays page...")
    page_ctx = get_page_context('misc')
    RELAY_SET.write_misc(template="all.html", path="misc/all.html", page_ctx=page_ctx)
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] [{get_memory_usage()}] Progress: Generated all relays page")

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
    page_ctx = get_page_context('misc')
    for k, v in misc_pages.items():
        RELAY_SET.write_misc(
            template="misc-families.html",
            path="misc/families-{}.html".format(k),
            sorted_by=v,
            page_ctx=page_ctx,
        )
        RELAY_SET.write_misc(
            template="misc-networks.html",
            path="misc/networks-{}.html".format(k),
            sorted_by=v,
            page_ctx=page_ctx,
        )
        RELAY_SET.write_misc(
            template="misc-contacts.html",
            path="misc/contacts-{}.html".format(k),
            sorted_by=v,
            page_ctx=page_ctx,
        )
        RELAY_SET.write_misc(
            template="misc-countries.html",
            path="misc/countries-{}.html".format(k),
            sorted_by=v,
            page_ctx=page_ctx,
        )
        RELAY_SET.write_misc(
            template="misc-platforms.html",
            path="misc/platforms-{}.html".format(k),
            sorted_by=v,
            page_ctx=page_ctx,
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
