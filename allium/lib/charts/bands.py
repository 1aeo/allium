"""Frozen write/read role bands.

Do not recompute percentiles from the live Onionoo dump. A network-wide
event would move live p10/p98 and hide itself. Rebuild
``data/role_ratio_bands.json`` from a quiet snapshot when the role mix
changes.
"""

import json
import os

from .identity import role_from_flags

# Global fallbacks used only if a role is missing from the catalog.
RATIO_LO = 0.90
RATIO_HI = 1.15
RATIO_INVESTIGATE_LO = 0.80
RATIO_INVESTIGATE_HI = 1.50
# Write/read strip display scale. Always reserve a top Investigate shelf.
RATIO_SCALE_LO = 0.50
RATIO_SCALE_HI = 1.70
RATIO_LEGEND_SHELF = 0.52
MIN_TOP_INVESTIGATE = 0.12
RAISED_TOP_INVESTIGATE = 0.18

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_BANDS_PATH = os.path.join(_DATA_DIR, "role_ratio_bands.json")

_CATALOG = None


def role_bands_path():
    """Path to the shipped frozen census file."""
    return _BANDS_PATH


def load_role_bands(path=None):
    """Load the frozen catalog. Cached after the first successful read."""
    global _CATALOG
    if path is None and _CATALOG is not None:
        return _CATALOG
    catalog_path = path or _BANDS_PATH
    with open(catalog_path, "r", encoding="utf-8") as handle:
        catalog = json.load(handle)
    if path is None:
        _CATALOG = catalog
    return catalog


def bands_frozen_from(catalog=None):
    catalog = catalog if catalog is not None else load_role_bands()
    return (catalog or {}).get("frozen_from") or ""


def bands_for_flags(flags, catalog=None):
    """Typical / uncommon / investigate row for this relay's flag set."""
    catalog = catalog if catalog is not None else load_role_bands()
    role = role_from_flags(flags)
    row = ((catalog or {}).get("roles") or {}).get(role)
    if not row:
        return {
            "role": role,
            "typical_lo": RATIO_LO,
            "typical_hi": RATIO_HI,
            "invest_lo": RATIO_INVESTIGATE_LO,
            "invest_hi": RATIO_INVESTIGATE_HI,
            "n": 0,
        }
    out = {"role": role}
    out.update(row)
    return out


def ratio_strip_data_hi(invest_hi, invest_lo=None):
    """Display-scale top of the write/read strip (below the legend shelf).

    Always reserves a visible Investigate band above this role's p98.
    Exit+Guard p98 is 1.71, so the 1.70 clip is raised rather than
    leaving a hairline of red.
    """
    ihi = float(invest_hi)
    room = RATIO_SCALE_HI - ihi
    if room + 1e-9 >= MIN_TOP_INVESTIGATE:
        return RATIO_SCALE_HI
    if invest_lo is None:
        span = RAISED_TOP_INVESTIGATE
    else:
        span = max(float(invest_lo) - RATIO_SCALE_LO, RAISED_TOP_INVESTIGATE)
    return ihi + span


def band_legend_labels(bands):
    """Locked range_pct copy: judgment + numeric range + percentile."""
    bands = bands or {
        "role": "all relays",
        "typical_lo": RATIO_LO,
        "typical_hi": RATIO_HI,
        "invest_lo": RATIO_INVESTIGATE_LO,
        "invest_hi": RATIO_INVESTIGATE_HI,
        "n": 0,
    }
    tlo, thi = bands["typical_lo"], bands["typical_hi"]
    ilo, ihi = bands["invest_lo"], bands["invest_hi"]
    rng_t = "{:.2f}–{:.2f}".format(tlo, thi)
    rng_u = "{:.2f}–{:.2f} or {:.2f}–{:.2f}".format(ilo, tlo, thi, ihi)
    rng_i = "<{:.2f} or >{:.2f}".format(ilo, ihi)
    return {
        "typical": "Typical  {}  ·  p10–p90".format(rng_t),
        "uncommon": "Uncommon  {}  ·  p2–p10 / p90–p98".format(rng_u),
        "investigate": "Investigate  {}  ·  <p2 or >p98".format(rng_i),
    }


def format_frozen_baseline(frozen_from):
    """``2026-08-15 19:00:00`` → ``15 Aug 2026``."""
    if not frozen_from:
        return ""
    try:
        date_part = str(frozen_from).split(" ", 1)[0]
        year, month, day = date_part.split("-")
        months = (
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        )
        return "{} {} {}".format(int(day), months[int(month) - 1], year)
    except (TypeError, ValueError, IndexError):
        return str(frozen_from)


def census_footnote(bands, frozen_from=""):
    """``4,444 Guards · baseline 15 Aug 2026``."""
    from .identity import peers_word

    peers = peers_word(bands)
    n = (bands or {}).get("n") or 0
    when = format_frozen_baseline(frozen_from) or "15 Aug 2026"
    if n:
        return "{:,} {} · baseline {}".format(n, peers, when)
    return "{} · baseline {}".format(peers, when)
