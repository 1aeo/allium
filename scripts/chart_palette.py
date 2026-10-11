#!/usr/bin/env python3
"""Choose raster.PALETTE, the 64 colors PNG charts are snapped to, from real charts.

Draws the charts of a random sample of relays and operators from the cached
Onionoo data (allium/data/cache, written by a build with --apis all) in full
color, then keeps:

- every color the drawing calls name (svg.py's colors, the callout box), exact;
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
import sys
from types import SimpleNamespace

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from allium.lib.charts import raster  # noqa: E402
from allium.lib.charts.render import ChartWriter  # noqa: E402

SIZE, EXACT = 64, 28


def sample_charts(relay_count, contact_count):
    cache = os.path.join(ROOT, "allium", "data", "cache")
    data = {name: json.load(open(os.path.join(cache, "onionoo_%s.json" % name)))
            for name in ("details", "bandwidth", "uptime")}
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
    named = set()
    for svg in charts:
        for op in svg.ops:
            if op[0] in ("text", "line", "rect"):
                named.add(op[5])
            if op[0] == "rect" and op[7]:
                named.add(op[7])
            if op[0] == "path":
                named.update(c for c in (op[2], op[5]) if c != "none")
    colors, counts = [], []
    for svg in charts:
        surface, rows, _width, _height = raster.render(svg, 2)
        found, found_counts = np.unique(np.ascontiguousarray(rows).view("<u4") & 0xFFFFFF, return_counts=True)
        surface.finish()
        colors.append(found)
        counts.append(found_counts)
    colors, inverse = np.unique(np.concatenate(colors), return_inverse=True)
    counts = np.bincount(inverse, np.concatenate(counts))
    rgb = np.stack([colors & 255, (colors >> 8) & 255, colors >> 16], 1).astype(np.float64)
    pinned = [np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], np.float64) for c in sorted(named)]
    order = np.argsort(-counts)
    for i in order:
        if len(pinned) >= EXACT:
            break
        if all(np.abs(rgb[i] - p).max() > 0 for p in pinned):
            pinned.append(rgb[i])
    exact = {tuple(p) for p in pinned}
    rest = np.array([i for i in order if tuple(rgb[i]) not in exact])
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
