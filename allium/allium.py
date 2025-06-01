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
    parser.add_argument(
        "--display-bandwidth-units",
        dest="bandwidth_units",
        choices=['bits', 'bytes'],
        default='bits',
        help="display bandwidth in bits/second (Kbit/s, Mbit/s, Gbit/s) or bytes/second (KB/s, MB/s, GB/s). Default: bits",
    )
    args = parser.parse_args()

    # object containing onionoo data and processing routines
    RELAY_SET = Relays(args.output_dir, args.onionoo_url, args.bandwidth_units == 'bits')
    if RELAY_SET.json == None:
        sys.exit(0)

    RELAY_SET.create_output_dir()

    # index and "all" HTML relay sets; index set limited to 500 relays
    RELAY_SET.write_misc(
        template="index.html",
        path="index.html",
        path_prefix="./",
        is_index=True,
    )
    RELAY_SET.write_misc(template="all.html", path="misc/all.html")

    # miscellaneous page filename suffixes and sorted-by keys
    misc_pages = {
        "by-bandwidth": "1.bandwidth",
        "by-consensus-weight": "1.consensus_weight_fraction,1.bandwidth",
        "by-exit-count": "1.exit_count,1.bandwidth",
        "by-middle-count": "1.middle_count,1.bandwidth",
        "by-first-seen": "1.first_seen,1.bandwidth",
    }

    # miscellaneous-sorted (per misc_pages k/v) HTML pages
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

    for k in keys:
        RELAY_SET.write_pages_by_key(k)

    # per-relay info pages
    RELAY_SET.write_relay_info()

    # copy static directory and its contents if it doesn't exist
    if not os.path.exists(os.path.join(args.output_dir, "static")):
        copytree(
            os.path.join(ABS_PATH, "static"),
            os.path.join(args.output_dir, "static"),
        )
