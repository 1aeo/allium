"""Frozen write/read role bands. Do not recompute from the live dump."""

import json
import os

from .identity import peers_word, role_from_flags

# Global fallbacks used only if a role is missing from the catalog.
_DEFAULT_BANDS = {"typical_lo": 0.90, "typical_hi": 1.15, "invest_lo": 0.80, "invest_hi": 1.50, "n": 0}
# Write/read strip display scale. Always reserve a top Investigate shelf.
RATIO_SCALE_LO = 0.50
RATIO_SCALE_HI = 1.70
MIN_TOP_INVESTIGATE = 0.12
RAISED_TOP_INVESTIGATE = 0.18
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "role_ratio_bands.json"),
          encoding="utf-8") as _handle:
    CATALOG = json.load(_handle)


def bands_for_role(role):
    """Typical / uncommon / investigate row for one role (``role_from_flags``)."""
    return dict(CATALOG["roles"].get(role) or _DEFAULT_BANDS, role=role)


def bands_for_flags(flags):
    return bands_for_role(role_from_flags(flags))


def ratio_strip_data_hi(bands):
    """Display-scale top of the write/read strip.

    Always reserves a visible Investigate band above this role's p98.
    Exit+Guard p98 is 1.71, so the 1.70 clip is raised rather than
    leaving a hairline of red.
    """
    ihi = float(bands["invest_hi"])
    if RATIO_SCALE_HI - ihi + 1e-9 >= MIN_TOP_INVESTIGATE:
        return RATIO_SCALE_HI
    return ihi + max(float(bands["invest_lo"]) - RATIO_SCALE_LO, RAISED_TOP_INVESTIGATE)


def band_legend_labels(bands):
    """Locked range_pct copy: judgment + numeric range + percentile."""
    tlo, thi, ilo, ihi = bands["typical_lo"], bands["typical_hi"], bands["invest_lo"], bands["invest_hi"]
    return (
        "Typical  {:.2f}–{:.2f}  ·  p10–p90".format(tlo, thi),
        "Uncommon  {:.2f}–{:.2f} or {:.2f}–{:.2f}  ·  p2–p10 / p90–p98".format(ilo, tlo, thi, ihi),
        "Investigate  <{:.2f} or >{:.2f}  ·  <p2 or >p98".format(ilo, ihi),
    )


def census_footnote(bands):
    """``4,444 Guards · baseline 15 Aug 2026``."""
    peers = peers_word(bands["role"])
    head = "{:,} {}".format(bands["n"], peers) if bands["n"] else peers
    date = str(CATALOG.get("frozen_from") or "").split(" ", 1)[0].split("-")
    if len(date) != 3:
        return head
    year, month, day = date
    return "{} · baseline {} {} {}".format(head, int(day), _MONTHS[int(month) - 1], year)
