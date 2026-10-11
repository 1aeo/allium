"""Frozen write/read role bands. Do not recompute from the live dump."""

import json
import os

from ..time_utils import parse_onionoo_timestamp

PEERS = {"Guard": "Guards", "Exit": "Exits", "Exit+Guard": "Exit+Guards", "Middle": "middle relays"}
# Write/read strip display scale. Always reserve a top Investigate shelf.
RATIO_SCALE_LO = 0.50
RATIO_SCALE_HI = 1.70
MIN_TOP_INVESTIGATE = 0.12
RAISED_TOP_INVESTIGATE = 0.18

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "role_ratio_bands.json"),
          encoding="utf-8") as _handle:
    CATALOG = json.load(_handle)
# The census day, for the footnote ("15 Aug 2026").
BASELINE = "{0.day} {0:%b %Y}".format(parse_onionoo_timestamp(CATALOG["frozen_from"]))


def role_from_flags(flags):
    """The catalog role for a relay's Onionoo flags: Exit+Guard, Exit, Guard or Middle."""
    flags = flags or ()
    if "Exit" in flags:
        return "Exit+Guard" if "Guard" in flags else "Exit"
    return "Guard" if "Guard" in flags else "Middle"


def bands_for_role(role):
    """The catalog's typical / investigate limits and census size for one role, with ``role`` and ``peers``."""
    return dict(CATALOG["roles"][role], role=role, peers=PEERS[role])


def ratio_strip_data_hi(bands):
    """Top of the write/read strip's scale.

    RATIO_SCALE_HI, unless that leaves under MIN_TOP_INVESTIGATE of red above
    this role's p98 (Middle 1.60, Exit+Guard 1.71): then the top Investigate
    shelf is made as tall as the bottom one (invest_lo - RATIO_SCALE_LO, at
    least RAISED_TOP_INVESTIGATE), so Middle tops out at 1.97 and Exit+Guard at 2.14.
    """
    ihi = bands["invest_hi"]
    if RATIO_SCALE_HI - ihi + 1e-9 >= MIN_TOP_INVESTIGATE:
        return RATIO_SCALE_HI
    return ihi + max(bands["invest_lo"] - RATIO_SCALE_LO, RAISED_TOP_INVESTIGATE)


def band_legend_labels(bands):
    """Legend text for the typical, uncommon and investigate patches: verdict, write/read range, census percentiles."""
    tlo, thi, ilo, ihi = bands["typical_lo"], bands["typical_hi"], bands["invest_lo"], bands["invest_hi"]
    return (
        "Typical  {:.2f}–{:.2f}  ·  p10–p90".format(tlo, thi),
        "Uncommon  {:.2f}–{:.2f} or {:.2f}–{:.2f}  ·  p2–p10 / p90–p98".format(ilo, tlo, thi, ihi),
        "Investigate  <{:.2f} or >{:.2f}  ·  <p2 or >p98".format(ilo, ihi),
    )


def census_footnote(bands):
    """``4,444 Guards · baseline 15 Aug 2026``."""
    return "{:,} {} · baseline {}".format(bands["n"], bands["peers"], BASELINE)
