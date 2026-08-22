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
import urllib.parse
from lib.charts.pipeline import (
    add_chart_arguments,
    apply_chart_html_flags,
    maybe_run_charts,
)
from lib.coordinator import create_relay_set_with_coordinator
from lib.progress_logger import ProgressLogger
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
    except PermissionError:
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



def validate_url_arguments(args):
    """
    Validate that all URL arguments use http:// or https:// scheme.
    Prevents potential SSRF via arbitrary URL schemes (e.g., file://, ftp://).
    
    Uses urllib.parse.urlsplit for robust scheme parsing rather than string
    prefix matching, which could be bypassed with schemes like "httpx://".
    
    --base-url is special: it accepts empty strings (the default), root-relative
    paths (starting with '/'), and http/https URLs for vanity URL generation.
    
    Args:
        args: argparse namespace with URL arguments
        
    Raises:
        SystemExit: If any URL argument uses an invalid scheme
    """
    url_fields = [
        ('onionoo_details_url', '--onionoo-details-url'),
        ('onionoo_uptime_url', '--onionoo-uptime-url'),
        ('onionoo_bandwidth_url', '--onionoo-bandwidth-url'),
        ('aroi_url', '--aroi-url'),
        ('exit_dns_health_url', '--exit-dns-health-url'),
        ('base_url', '--base-url'),
    ]
    for attr, flag_name in url_fields:
        url = getattr(args, attr, '')
        if not url:
            continue
        # --base-url accepts root-relative paths (e.g., "/metrics") in addition
        # to http/https URLs; all other URL arguments require a full URL.
        # Reject scheme-relative URLs like "//evil.example/..." which would
        # inherit the page's protocol and redirect to an attacker-controlled host.
        if attr == 'base_url' and url.startswith('/') and not url.startswith('//'):
            continue
        scheme = urllib.parse.urlsplit(url).scheme.lower()
        if scheme not in ('http', 'https'):
            print(f"❌ Error: {flag_name} must use http:// or https:// scheme")
            print(f"   Got: {url}")
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
        help=(
            'public base URL for vanity, canonical, Open Graph, and sitemap '
            'URLs (default: "" for root-relative local output)'
        ),
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
        "--exit-dns-health-url",
        dest="exit_dns_health_url",
        type=str,
        default="https://exitdnshealth.1aeo.com/latest.json",
        help=(
            "Exit DNS Health API HTTP URL (default "
            '"https://exitdnshealth.1aeo.com/latest.json")'
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
    add_chart_arguments(parser)
    args = parser.parse_args()

    # Validate URL arguments use safe schemes (defense-in-depth against SSRF)
    validate_url_arguments(args)

    start_time = time.time()
    
    # Progress step accounting - DERIVED from the structures that emit the
    # steps, so adding an API worker or page type updates the total
    # automatically (hard-coded 4+22+35 previously drifted: comments said
    # 57/59 while runs logged 61, and --apis details overcounted).
    from lib.coordinator import Coordinator
    from lib.site_generator import STANDALONE_PAGES, SORTED_PAGE_KEYS

    # Setup: starting, creating output dir, dir ready, init relay data
    setup_steps = 4

    # API fetching: section start + threaded-start + one start and one
    # complete per enabled worker + all-workers-complete + section end;
    # data processing: section start, creating relay set, created, section
    # end (intermediate messages log without incrementing the counter).
    enabled_workers = sum(
        1 for _ in Coordinator.iter_enabled_worker_entries(args.enabled_apis))
    coordinator_steps = (4 + 2 * enabled_workers) + 4

    # Page generation: details-loaded + section start, generating+generated
    # per standalone page, misc sorted pages x2, one completion per detail
    # page key, then relay pages / static files / search index / prometheus
    # metrics and search-discovery files x2 each, section end + completion message.
    page_generation_steps = (2 + 2 * len(STANDALONE_PAGES)
                             + 2 + len(SORTED_PAGE_KEYS)
                             + 2 + 2 + 2 + 2 + 2 + 2)

    total_steps = setup_steps + coordinator_steps + page_generation_steps

    # Create the single ProgressLogger threaded through the whole pipeline
    progress_logger = ProgressLogger(start_time, total_steps, args.progress)

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
        if RELAY_SET is None or RELAY_SET.json is None:
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
    
    # Template flags before Jinja so --no-charts / auto-without-extra omit
    # the History <img>. Does not import matplotlib.
    apply_chart_html_flags(RELAY_SET, args)

    # Generate the complete static site
    # Page definitions and generation logic are in lib/site_generator.py
    generate_site(RELAY_SET, args, progress_logger)

    # Chart pass after HTML. Default --charts auto is silent when the
    # extra is missing. matplotlib never runs inside Jinja workers.
    maybe_run_charts(RELAY_SET, args, progress_logger)
