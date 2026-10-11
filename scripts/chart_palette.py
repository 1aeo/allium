#!/usr/bin/env python3
"""Choose raster.PALETTE, the 64 colors PNG charts are snapped to, from real charts.

Draws the charts of a random sample of relays and operators from the cached
Onionoo data (allium/data/cache, written by a build with --apis all) in full
color, then keeps:

- every color the drawing calls name (svg.py's colors), exact;
- the most common other colors (the translucent bands and legend swatches
  blended over the background), exact, up to 28 in all;
- for the rest, the weighted means (k-means) of the remaining edge shades.

Prints the PALETTE lines to paste into allium/lib/charts/raster.py. Run it
after adding a color to the charts (tests/unit/charts/test_raster.py fails
until then).

usage: python3 scripts/chart_palette.py [RELAYS] [CONTACTS]
"""

import hashlib
import json
import os
import random
import re
import sys
from types import SimpleNamespace

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from allium.lib.charts import raster  # noqa: E402
from allium.lib.charts.render import ChartWriter  # noqa: E402

SIZE, EXACT = 64, 28


def sample_charts(relay_count, contact_count):
    def load(name):
        with open(os.path.join(ROOT, "allium", "data", "cache", "onionoo_%s.json" % name), encoding="utf-8") as handle:
            return json.load(handle)

    data = {name: load(name) for name in ("details", "bandwidth", "uptime")}
    relays = data["details"]["relays"]
    groups = {}
    for index, relay in enumerate(relays):
        groups.setdefault(hashlib.md5((relay.get("contact") or "").encode()).hexdigest(), []).append(index)
    writer = ChartWriter(SimpleNamespace(json={"relays": relays}, bandwidth_data=data["bandwidth"],
                                         uptime_data=data["uptime"]), "svg")
    drawn = []
    writer._save = lambda directory, name, draw, *args: drawn.append(draw(*args)) or 0
    rng = random.Random(1)
    for relay in rng.sample(relays, min(relay_count, len(relays))):
        writer.relay(relay, None)
    for key in rng.sample(sorted(groups), min(contact_count, len(groups))):
        writer.contact(groups[key], None)
    return [svg for svg in drawn if svg]


def main():
    relay_count, contact_count = (int(arg) for arg in (sys.argv[1:] + ["300", "100"])[:2])
    charts = sample_charts(relay_count, contact_count)
    # Every color a drawing call names, whatever the op ("none" and dash patterns are not colors).
    named = {v.lower() for svg in charts for op in svg.ops for v in op
             if isinstance(v, str) and re.fullmatch("#[0-9a-f]{6}", v, re.I)}
    census = []
    for svg in charts:
        surface, rows, _width, _height = raster.render(svg, 2)
        census.append(np.unique(np.ascontiguousarray(rows).view("<u4") & 0xFFFFFF, return_counts=True))
        surface.finish()
    colors, inverse = np.unique(np.concatenate([found for found, _counts in census]), return_inverse=True)
    counts = np.bincount(inverse, np.concatenate([found_counts for _found, found_counts in census]))
    rgb = np.stack([colors & 255, (colors >> 8) & 255, colors >> 16], 1).astype(np.float64)
    pinned = [np.array(list(bytes.fromhex(c[1:])), np.float64) for c in sorted(named)]
    named_rgb, extra = {tuple(p) for p in pinned}, max(0, EXACT - len(pinned))
    order = np.argsort(-counts)
    rest = [i for i in order if tuple(rgb[i]) not in named_rgb]  # the most common first
    pinned += [rgb[i] for i in rest[:extra]]
    rest = np.array(rest[extra:])
    free = []
    for i in rest:  # start from the most frequent remaining shades, not too close to a chosen color
        if all(np.abs(rgb[i] - p).max() > 12 for p in pinned + free):
            free.append(rgb[i])
        if len(pinned) + len(free) == SIZE:
            break
    centres = np.vstack(pinned + free)
    points, weights = rgb[rest], counts[rest]
    for _ in range(30):
        nearest = ((points[:, None, :] - centres[None]) ** 2).sum(-1).argmin(1)
        for j in range(len(pinned), SIZE):
            mine = nearest == j
            if mine.any():
                centres[j] = (points[mine] * weights[mine, None]).sum(0) / weights[mine].sum()
    palette = ["%02x%02x%02x" % tuple(int(round(v)) for v in c) for c in centres]
    print("# %d charts, %d colors, %.2f%% of pixels in the %d most common" % (
        len(charts), len(colors), 100.0 * counts[order[:SIZE]].sum() / counts.sum(), SIZE))
    print("PALETTE = (")
    for start in range(0, SIZE, 8):
        print('    "%s%s"' % (" ".join(palette[start:start + 8]), " " if start + 8 < SIZE else ""))
    print(").split()")


if __name__ == "__main__":
    main()
