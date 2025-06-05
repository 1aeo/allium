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
from shutil import copytree
from lib.relays import Relays

ABS_PATH = os.path.dirname(os.path.abspath(__file__))

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
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Starting allium static site generation...")

    # object containing onionoo data and processing routines
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Initializing relay data from onionoo...")
    RELAY_SET = Relays(args.output_dir, args.onionoo_url, args.bandwidth_units == 'bits')
    if RELAY_SET.json == None:
        sys.exit(0)
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Loaded relay data from onionoo - found {len(RELAY_SET.json.get('relays', []))} relays")

    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Creating output directory...")
    RELAY_SET.create_output_dir()
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Output directory ready at {args.output_dir}")

    # index and "all" HTML relay sets; index set limited to 500 relays
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Generating index page...")
    RELAY_SET.write_misc(
        template="index.html",
        path="index.html",
        path_prefix="./",
        is_index=True,
    )
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Generated index page with top 500 relays")

    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Generating all relays page...")
    RELAY_SET.write_misc(template="all.html", path="misc/all.html")
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Generated all relays page")

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
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Generating miscellaneous sorted pages...")
    for k, v in misc_pages.items():
        RELAY_SET.write_misc(
            template="misc-families.html",
            path="misc/families-{}.html".format(k),
            sorted_by=v,
        )
        RELAY_SET.write_misc(
            template="misc-networks.html",
            path="misc/networks-{}.html".format(k),
            sorted_by=v,
        )
        RELAY_SET.write_misc(
            template="misc-contacts.html",
            path="misc/contacts-{}.html".format(k),
            sorted_by=v,
        )
        RELAY_SET.write_misc(
            template="misc-countries.html",
            path="misc/countries-{}.html".format(k),
            sorted_by=v,
        )
        RELAY_SET.write_misc(
            template="misc-platforms.html",
            path="misc/platforms-{}.html".format(k),
            sorted_by=v,
        )

    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Generated 6 miscellaneous sorted pages")
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
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Generating pages by unique values...")
    for i, k in enumerate(keys):
        RELAY_SET.write_pages_by_key(k)
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Generated pages for {len(keys)} unique value types")

    # per-relay info pages
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Generating individual relay info pages...")
    RELAY_SET.write_relay_info()
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Generated individual pages for {len(RELAY_SET.json.get('relays', []))} relays")

    # copy static directory and its contents if it doesn't exist
    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Copying static files...")
    if not os.path.exists(os.path.join(args.output_dir, "static")):
        copytree(
            os.path.join(ABS_PATH, "static"),
            os.path.join(args.output_dir, "static"),
        )
        if args.progress:
            print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Copied static files to output directory")
    else:
        if args.progress:
            print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Static files already exist, skipping copy")

    if args.progress:
        print(f"[{time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}] [{(progress_step := progress_step + 1)}/{total_steps}] Progress: Allium static site generation completed successfully!")
