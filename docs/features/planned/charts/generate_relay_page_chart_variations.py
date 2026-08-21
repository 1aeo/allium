#!/usr/bin/env python3
"""Generate relay-page chart variations from live Onionoo example histories.

Reads:
  /tmp/onionoo/details.json
  /tmp/onionoo/uptime_examples.json
  /tmp/onionoo/bandwidth_examples.json

Writes PNGs to --out (default: this directory's mockups/) and --artifacts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from allium.lib.stability_utils import current_overload_status  # noqa: E402

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch
from matplotlib.transforms import ScaledTranslation

# Palette: red (BAD) is reserved for problems. Series and events that are
# not "wrong" use blue / purple / orange / navy / green.
BLUE = "#0072B2"
WRITE = "#6A3D9A"
GREEN = "#009E73"
SKY = "#56B4E9"
ORANGE = "#E69F00"
GRAY = "#666666"
NAVY = "#1B3A4B"
BAD = "#C0392B"
RESTART = NAVY
OVERLOAD = BAD
# Global fallback only. The strip uses frozen per-role bands from
# data/role_ratio_bands.json (this flag set's p10–p90 / beyond p98).
# Do not recompute those from live Onionoo — a DoS that hits every Exit
# would move a live percentile and hide the event.
RATIO_LO = 0.90
RATIO_HI = 1.15
RATIO_INVESTIGATE_LO = 0.80
RATIO_INVESTIGATE_HI = 1.50
AMBER = ORANGE
ROLE_BANDS_PATH = Path(__file__).resolve().parent / "data" / "role_ratio_bands.json"
TH4R = "27A06581F1CE22D1BA4D160F6E7C7AABAC176242"
F3NETZE = "3C89C80E2699FB6358BBB64FDC9547AFCB5C03F7"
PIRATE = "DD32947397C5E6A5FC0D6A6BBE5CD008DEC1A60B"
# 1aeo.com Guard+HSDir, effective family 241, not currently overloaded.
JEANGRAE = "02B1C5DFBCBEC735435652050DE1AF0BB0B108CF"
# Exit-only and Middle examples for the four frozen write/read band sets.
ZARATHUSTRA = "E70906B974DF23A6858B06FED589DC3696781F00"
TENDXX = "F538DBEA80CA7DA733537166CA364D98CBE9E1D1"

PERIOD_META = {
    "1_month": {
        "short": "1M", "title": "1 month", "bucket": "4-hour",
        "interval_hours": 4, "nominal_days": 30,
    },
    "6_months": {
        "short": "6M", "title": "6 months", "bucket": "12-hour",
        "interval_hours": 12, "nominal_days": 180,
    },
    "1_year": {
        "short": "1Y", "title": "1 year", "bucket": "2-day",
        "interval_hours": 48, "nominal_days": 365,
    },
    "5_years": {
        "short": "5Y", "title": "5 years", "bucket": "10-day",
        "interval_hours": 240, "nominal_days": 1825,
    },
}
PERIOD_ORDER = ("1_month", "6_months", "1_year", "5_years")
# Bandwidth graphs use coarser buckets than /uptime (1-day / 1-day / 2-day / 10-day).
BW_PERIOD_META = {
    "1_month": {
        "short": "1M", "title": "1 month", "bucket": "1-day",
        "interval_hours": 24, "nominal_days": 30,
    },
    "6_months": {
        "short": "6M", "title": "6 months", "bucket": "1-day",
        "interval_hours": 24, "nominal_days": 180,
    },
    "1_year": {
        "short": "1Y", "title": "1 year", "bucket": "2-day",
        "interval_hours": 48, "nominal_days": 365,
    },
    "5_years": {
        "short": "5Y", "title": "5 years", "bucket": "10-day",
        "interval_hours": 240, "nominal_days": 1825,
    },
}

# 400-relay Onionoo 1_month sample, relays_published 2026-08-15 17:00 UTC.
# Median imperfect rate ~3.1%. These interval midpoints were ≥8%.
NETWORK_GAP_MIDPOINTS = (
    "2026-07-19 18:00:00",
    "2026-07-28 10:00:00",
    "2026-07-28 14:00:00",
)

FLAG_CMAP = LinearSegmentedColormap.from_list(
    "flag", [BAD, ORANGE, GREEN], N=256
)


def style():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#cccccc",
        "axes.grid": True,
        "grid.color": "#eeeeee",
        "grid.linewidth": 0.8,
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "legend.frameon": False,
        "figure.dpi": 140,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.08,
        "savefig.dpi": 140,
    })


def parse_onionoo_ts(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def parse_ms(ms):
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def history_series(block):
    if not block or not block.get("values"):
        return [], []
    first = parse_onionoo_ts(block["first"])
    interval = int(block.get("interval") or 0)
    factor = float(block.get("factor") or 1)
    ts, vals = [], []
    for i, raw in enumerate(block["values"]):
        if raw is None:
            continue
        ts.append(first + timedelta(seconds=i * interval))
        vals.append(raw * factor)
    return ts, vals


def as_pct(vals):
    if not vals:
        return []
    if max(vals) <= 1.5:
        return [v * 100.0 for v in vals]
    if max(vals) > 20:
        return [v / 9.99 for v in vals]
    return list(vals)


def bytes_to_mbit(vals):
    return [v * 8.0 / 1_000_000.0 for v in vals]


def by_fp(doc):
    return {r["fingerprint"]: r for r in doc.get("relays", [])}


def _trim_rgba(rgba, pad_px=12, white=250):
    """Crop outer white from a canvas dump. savefig(bbox='tight') re-anchors
    out-of-axes legends and opens a gap under the date labels.
    """
    rgb = rgba[:, :, :3]
    ink = rgb.min(axis=2) < white
    rows = np.where(ink.any(axis=1))[0]
    cols = np.where(ink.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return rgba
    y0 = max(0, int(rows[0]) - pad_px)
    y1 = min(rgb.shape[0], int(rows[-1]) + pad_px + 1)
    x0 = max(0, int(cols[0]) - pad_px)
    x1 = min(rgb.shape[1], int(cols[-1]) + pad_px + 1)
    return rgba[y0:y1, x0:x1]


def save(fig, paths, *, trim=False):
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        if trim:
            fig.canvas.draw()
            rgba = np.asarray(fig.canvas.buffer_rgba())
            plt.imsave(p, _trim_rgba(rgba))
        else:
            fig.savefig(p)
    plt.close(fig)


def _text_just_under(fig, artist, text, *, fontsize, color, offset_pt=5,
                     va="top", style=None):
    """Pin a note to an artist so bbox=tight cannot keep a figure-bottom slab."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bbox = artist.get_window_extent(renderer)
    x0, y0 = fig.transFigure.inverted().transform((bbox.x0, bbox.y0))
    trans = fig.transFigure + ScaledTranslation(
        0, -offset_pt / 72.0, fig.dpi_scale_trans,
    )
    kw = dict(
        fontsize=fontsize, color=color, va=va, ha="left", transform=trans,
    )
    if style:
        kw["style"] = style
    return fig.text(x0, y0, text, **kw)


def caption(fig, published, story, y=0.012, footnote=None, under=None):
    wrapped = textwrap.fill(story, width=108)
    note = f"{footnote}\n" if footnote else ""
    text = (
        f"{note}{wrapped}\n"
        f"Source: Onionoo  ·  relays_published {published} UTC  ·  "
        f"Allium relay-page mockup"
    )
    if under is not None:
        _text_just_under(fig, under, text, fontsize=8, color=GRAY, offset_pt=6)
        return
    fig.text(0.01, y, text, fontsize=8, color=GRAY, va="bottom")


def date_axis(ax):
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))


def dip_spans(ts, pct, thresh=99.0):
    spans = []
    start = None
    for i, v in enumerate(pct):
        if v < thresh:
            if start is None:
                start = i
        elif start is not None:
            spans.append((start, i - 1))
            start = None
    if start is not None:
        spans.append((start, len(ts) - 1))
    return spans


def mean_min(pct):
    return float(np.mean(pct)), float(np.min(pct))


def bucket_window(ts, interval_hours=4):
    """Onionoo first/last are interval midpoints. Return (start, end) UTC."""
    half = timedelta(hours=interval_hours / 2)
    return ts - half, ts + half


def summarize_uptime(ts, pct, interval_hours=4):
    avg = float(np.mean(pct)) if pct else 0.0
    imperfect = [(t, v) for t, v in zip(ts, pct) if v < 99.5]
    worst = min(imperfect, key=lambda x: x[1]) if imperfect else None
    by_level = {50: [], 75: [], 25: [], 0: []}
    for t, v in imperfect:
        if v < 12.5:
            by_level[0].append(t)
        elif v < 37.5:
            by_level[25].append(t)
        elif v < 62.5:
            by_level[50].append(t)
        else:
            by_level[75].append(t)
    return {
        "avg": avg,
        "n": len(pct),
        "perfect": len(pct) - len(imperfect),
        "imperfect": imperfect,
        "worst": worst,
        "by_level": by_level,
        "interval_hours": interval_hours,
    }


def fmt_window(ts, interval_hours=4):
    start, end = bucket_window(ts, interval_hours)
    return f"{start.strftime('%-d %b %H:%M')}–{end.strftime('%H:%M')} UTC"


# Discrete Onionoo 4-hour / hourly-consensus steps
UPTIME_LEVELS = [0, 25, 50, 75, 100]
UPTIME_LEVEL_COLORS = [BAD, "#E07A5F", ORANGE, "#E8E07A", GREEN]
UPTIME_LEVEL_LABELS = [
    "0/4 hours",
    "1/4 hours",
    "2/4 hours",
    "3/4 hours",
    "4/4 hours",
]


# ---------------------------------------------------------------------------
# Chart 5 — uptime variations (th4r, 1 month)
# ---------------------------------------------------------------------------

def uptime_a_annotated_line(ts, pct, published, out_paths):
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    fig.subplots_adjust(bottom=0.20)
    ax.plot(ts, pct, color=BLUE, linewidth=1.8, label="Running flag")
    ax.scatter(ts, pct, s=10, color=BLUE, zorder=3)
    spans = dip_spans(ts, pct)
    for i, (a, b) in enumerate(spans):
        lo = min(pct[a:b + 1])
        mid_t = ts[a] + (ts[b] - ts[a]) / 2
        ax.plot(ts[a:b + 1], pct[a:b + 1], color=BAD, linewidth=2.4, zorder=4)
        ax.annotate(
            f"{ts[a].strftime('%b %d %H:%M')}\n{lo:.0f}% of 4h window",
            xy=(mid_t, lo),
            xytext=(0, -28 if i % 2 == 0 else -48),
            textcoords="offset points",
            ha="center", va="top", fontsize=7.5, color=BAD,
            arrowprops=dict(arrowstyle="-", color=BAD, lw=0.7),
        )
    ax.set_ylim(35, 104)
    ax.set_ylabel("Share of 4-hour window with Running (%)")
    ax.set_title("Uptime A — annotated line   ·   th4r (Guard, DE)")
    date_axis(ax)
    avg, lo = mean_min(pct)
    ax.legend(loc="lower left")
    caption(
        fig, published,
        f"Story: four outage events ({len(spans)} spans, {sum(1 for v in pct if v < 99)} "
        f"four-hour buckets) in 31 days, none a process restart "
        f"(last_restarted 2025-10-01). Month average {avg:.1f}%, worst bucket {lo:.0f}%.",
    )
    save(fig, out_paths)


def uptime_b_area_threshold(ts, pct, published, extra, out_paths):
    stats = summarize_uptime(ts, pct)
    fig = plt.figure(figsize=(11.2, 7.4))
    ax = fig.add_axes([0.08, 0.38, 0.90, 0.52])
    arr = np.array(pct)
    ax.fill_between(ts, arr, 0, color=BLUE, alpha=0.16, linewidth=0)
    ax.plot(ts, pct, color=BLUE, linewidth=1.7, label="Running in each 4-hour bucket")
    below = arr < 98
    if below.any():
        ax.fill_between(
            ts, arr, 98, where=below, color=BAD, alpha=0.35,
            interpolate=True, label="Bucket below 98% (missed ≥1 hourly consensus)",
        )
    ax.axhline(
        98, color=ORANGE, linestyle="--", linewidth=1.2,
        label="98% — Guard and HSDir WFU floor (not a countdown)",
    )
    ax.axhline(
        stats["avg"], color=NAVY, linestyle=":", linewidth=1.2,
        label=f"1-month average {stats['avg']:.1f}%  (same number as #uptime)",
    )
    if stats["worst"]:
        wt, wv = stats["worst"]
        ax.scatter([wt], [wv], s=42, color=BAD, zorder=5)
        ax.annotate(
            f"Worst bucket  {wv:.0f}%  once\n{fmt_window(wt)}\n"
            f"(2 of 4 hourly consensuses)",
            xy=(wt, wv), xytext=(18, -8), textcoords="offset points",
            fontsize=8, color=BAD,
            arrowprops=dict(arrowstyle="->", color=BAD, lw=0.8),
        )
    ax.set_ylim(35, 106)
    ax.set_ylabel("Hourly consensuses with Running, packed into Onionoo's 4-hour bucket")
    ax.set_title("Uptime B — area + real 98% WFU floor   ·   th4r (Guard, DE)")
    date_axis(ax)
    ax.legend(loc="lower left", fontsize=8)

    # Self-explaining flag rules — 95% was a mockup heuristic, not a Tor timer.
    rules = (
        "There is no “N hours below 95% → lose flag X.” Authorities do not use this chart.\n"
        "  Running   lost in ~45 minutes if directory authorities cannot connect. "
        "One missed hourly consensus → a 75% (3/4) bucket.\n"
        "  Guard     requires Weighted Fractional Uptime ≥98%. WFU weights recent downtime "
        "more than this monthly average — a fresh dip hurts more than an old one.\n"
        "  HSDir     same 98% WFU, plus Stable. This relay's HSDir was present only "
        f"{extra['hsdir_1m']:.1f}% of the month (currently missing). "
        "Flag Uptime on the page follows Guard and hides that.\n"
        "  Stable    uptime or weighted MTBF vs the network median (typically weeks). "
        "One consensus-visible outage can reset the clock. Not a percentage of the month."
    )
    fig.text(0.08, 0.245, rules, fontsize=8, color=NAVY, va="top", family="DejaVu Sans",
             linespacing=1.35)

    n50 = len(stats["by_level"][50])
    n75 = len(stats["by_level"][75])
    seventy_five = "; ".join(fmt_window(t) for t in stats["by_level"][75])
    box = (
        f"Numbers that belong on #uptime  (computed from the same Onionoo 1_month series)\n"
        f"  1-month average     {stats['avg']:.1f}%     "
        f"{stats['perfect']}/{stats['n']} buckets at 100%     "
        f"health row today truncates this to {int(stats['avg'])}%\n"
        f"  Imperfect buckets   {len(stats['imperfect'])} of {stats['n']}\n"
        f"  Worst               50%  × {n50}     {fmt_window(stats['worst'][0]) if stats['worst'] else '—'}\n"
        f"  75% (1 of 4 missed) × {n75}     {seventy_five}\n"
        f"  Process restart     none in this window     last_restarted {extra['last_restarted']}  "
        f"(Current Status on the page is this, not the chart)"
    )
    fig.text(0.08, 0.012, box + f"\nSource: Onionoo  ·  relays_published {published} UTC",
             fontsize=8, color=GRAY, va="bottom", family="DejaVu Sans",
             linespacing=1.35)
    save(fig, out_paths)


def uptime_c_heatmap(ts, pct, published, extra, out_paths):
    stats = summarize_uptime(ts, pct)
    hours = sorted({t.hour for t in ts})
    dates = sorted({t.date() for t in ts}, reverse=True)
    mat = np.full((len(dates), len(hours)), np.nan)
    for t, v in zip(ts, pct):
        mat[dates.index(t.date()), hours.index(t.hour)] = v

    cmap = ListedColormap(UPTIME_LEVEL_COLORS)
    norm = BoundaryNorm([-0.1, 12.5, 37.5, 62.5, 87.5, 100.1], cmap.N)

    fig, ax = plt.subplots(figsize=(11.2, 7.0))
    fig.subplots_adjust(bottom=0.22)
    mesh = ax.imshow(mat, aspect="auto", cmap=cmap, norm=norm, interpolation="nearest")
    # Column labels are the actual 4-hour windows (midpoint ± 2h)
    col_labels = []
    for h in hours:
        start = (h - 2) % 24
        end = (h + 2) % 24
        col_labels.append(f"{start:02d}–{end:02d}")
    ax.set_xticks(range(len(hours)), col_labels)
    tick_idx = list(range(0, len(dates), 2))
    ax.set_yticks(tick_idx, [dates[i].strftime("%b %d") for i in tick_idx])
    ax.set_xlabel(
        "UTC window  ·  Onionoo 1_month only (4-hour buckets). "
        "6_months uses 12-hour buckets; 1_year uses 2-day buckets — no time-of-day there."
    )
    ax.set_title("Uptime C — time-of-day heatmap   ·   th4r (Guard, DE)")
    ax.grid(False)
    for y, x in zip(*np.where(~np.isnan(mat) & (mat < 99.5))):
        hours_up = int(round(mat[y, x] / 25.0))
        ax.text(x, y, f"{hours_up}/4", ha="center", va="center",
                fontsize=7.5, color="white", fontweight="bold")
    cbar = fig.colorbar(mesh, ax=ax, fraction=0.03, pad=0.02, ticks=UPTIME_LEVELS)
    cbar.ax.set_yticklabels(UPTIME_LEVEL_LABELS)
    cbar.set_label("Hourly consensuses with Running")
    caption(
        fig, published,
        "Why only 0 / 25 / 50 / 75 / 100? Consensuses are hourly. A 4-hour bucket "
        "holds 4 samples, so Onionoo stores 0, 249, 499, 749, or 999 "
        f"(× 1/999). th4r: 181×4/4, 4×3/4, 1×2/4 (worst {fmt_window(stats['worst'][0]) if stats['worst'] else '—'}). "
        "Why 30 days? Onionoo's finest published uptime graph is 1_month. "
        "1_week was removed in 2020.",
    )
    save(fig, out_paths)


def uptime_section_numbers(ts, pct, published, extra, out_paths):
    """Mock of the numbers to add beside the existing #uptime scalars."""
    stats = summarize_uptime(ts, pct)
    fig, ax = plt.subplots(figsize=(11.2, 5.8))
    ax.axis("off")
    ax.set_title("Proposed #uptime numbers  ·  same Onionoo series as charts B/C  ·  th4r",
                 loc="left", pad=8)

    rows = [
        ["Field", "On the relay page today", "From this 1-month series"],
        ["1-month Running average",
         f"{stats['avg']:.1f}% in Overall Uptime 1M/6M/1Y/5Y\n"
         f"Health row shows UP {int(stats['avg'])}% (truncated)",
         f"{stats['avg']:.1f}%   ({stats['perfect']}/{stats['n']} buckets at 100%)"],
        ["Current Status",
         f"UP since last_restarted\n{extra['last_restarted']}  (process clock)",
         "Not the chart. Process did not restart.\nThese dips are missed hourly consensuses."],
        ["Imperfect 4-hour buckets",
         "Not shown",
         f"{len(stats['imperfect'])} of {stats['n']}"],
        ["Worst bucket",
         "Not shown",
         f"50%  × once   {fmt_window(stats['worst'][0])}\n2 of 4 hourly consensuses missing"],
        ["75% buckets (1 of 4 missed)",
         "Not shown",
         f"× {len(stats['by_level'][75])}\n" +
         ";  ".join(fmt_window(t) for t in stats["by_level"][75][:2]) + "\n" +
         ";  ".join(fmt_window(t) for t in stats["by_level"][75][2:])],
        ["Flag Uptime (page)",
         "Follows Guard → “Matches Overall”\nHSDir 59.1% is not displayed",
         f"Guard {extra['guard_1m']:.1f}%   HSDir {extra['hsdir_1m']:.1f}%\n"
         "HSDir currently missing — needs the swimlane"],
    ]

    table = ax.table(
        cellText=rows[1:], colLabels=rows[0], loc="center", cellLoc="left",
        colWidths=[0.22, 0.40, 0.38],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 2.4)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#dddddd")
        if r == 0:
            cell.set_facecolor("#1B3A4B")
            cell.set_text_props(color="white", fontweight="bold")
        elif r % 2 == 0:
            cell.set_facecolor("#f7f7f7")
    caption(
        fig, published,
        "Add the right-hand column under #uptime next to the existing 1M/6M/1Y/5Y "
        "scalars. Do not replace Current Status — keep process uptime, and label it "
        "as last_restarted so it is not confused with consensus Running.",
    )
    save(fig, out_paths)


def network_gap_spans(interval_hours=4):
    half = timedelta(hours=interval_hours / 2)
    windows = []
    for raw in NETWORK_GAP_MIDPOINTS:
        mid = parse_onionoo_ts(raw)
        windows.append((mid - half, mid + half))
    windows.sort()
    merged = []
    for start, end in windows:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def in_network_gap(ts, interval_hours=4):
    for start, end in network_gap_spans(interval_hours):
        if start <= ts <= end:
            return True
    return False


def uptime_b_two_clocks(ts, pct, published, last_restarted, nickname, out_paths):
    """Network-visible Running vs Tor process, plus shared network gaps."""
    stats = summarize_uptime(ts, pct)
    fig, (ax, axp) = plt.subplots(
        2, 1, figsize=(11.2, 6.6), sharex=True,
        gridspec_kw={"height_ratios": [4.0, 0.62], "hspace": 0.08},
    )
    fig.subplots_adjust(bottom=0.18, top=0.88)
    arr = np.array(pct)
    local = np.array([
        (v < 99) and not in_network_gap(t) for t, v in zip(ts, pct)
    ])
    shared = np.array([
        (v < 99) and in_network_gap(t) for t, v in zip(ts, pct)
    ])

    for start, end in network_gap_spans():
        ax.axvspan(start, end, color=GRAY, alpha=0.22, zorder=0)
        axp.axvspan(start, end, color=GRAY, alpha=0.22, zorder=0)

    ax.fill_between(ts, arr, 0, color=BLUE, alpha=0.14, linewidth=0)
    ax.plot(ts, pct, color=BLUE, linewidth=1.7, zorder=3,
            label="Network-visible Running (authorities)")
    if local.any():
        ax.fill_between(
            ts, arr, 98, where=local, color=BAD, alpha=0.40,
            interpolate=True, zorder=2,
        )
    if shared.any():
        ax.fill_between(
            ts, arr, 98, where=shared, color=ORANGE, alpha=0.45,
            interpolate=True, zorder=2,
        )
    ax.axhline(98, color=ORANGE, linestyle="--", linewidth=1.1)
    ax.set_ylim(35, 106)
    ax.set_ylabel("Network-visible Running (%)")
    ax.set_title(
        f"Network-visible Running   ·   {nickname}\n"
        "Not Tor process uptime — authorities listing this relay as Running"
    )
    date_axis(ax)
    ax.legend(
        handles=[
            Line2D([0], [0], color=BLUE, linewidth=1.7,
                   label="Network-visible Running (this relay)"),
            Patch(facecolor=BAD, alpha=0.45,
                  label="This relay missed a consensus · network was fine"),
            Patch(facecolor=ORANGE, alpha=0.50,
                  label="This relay missed a consensus many relays also missed"),
            Patch(facecolor=GRAY, alpha=0.35,
                  label="Network-wide gap (sample ≥8% imperfect)"),
        ],
        loc="lower left", fontsize=8,
    )

    restarted = parse_onionoo_ts(last_restarted) if last_restarted else None
    axp.set_ylim(0, 1)
    axp.set_yticks([0.5], ["Tor process"])
    axp.fill_between(ts, 0, 1, color=GREEN, alpha=0.35, linewidth=0)
    if restarted and ts[0] <= restarted <= ts[-1]:
        axp.axvline(restarted, color=NAVY, linestyle="-.", linewidth=1.8)
        ax.axvline(restarted, color=NAVY, linestyle="-.", linewidth=1.2, alpha=0.7)
        axp.text(
            restarted, 0.5,
            f"  restarted {restarted.strftime('%-d %b %H:%M')}",
            va="center", fontsize=8, color=NAVY,
        )
    else:
        when = restarted.strftime("%-d %b %Y") if restarted else "unknown"
        axp.text(
            ts[0], 0.5,
            f"  Up since {when}  ·  no restart in this window",
            va="center", fontsize=8, color=NAVY,
        )
    axp.set_xlabel("")
    date_axis(axp)

    n_local = int(local.sum())
    n_shared = int(shared.sum())
    caption(
        fig, published,
        f"Two clocks the operator controls: process (bottom rail, last_restarted) "
        f"and network-visible Running (top, month average {stats['avg']:.1f}%). "
        f"{n_local} local gap(s), {n_shared} shared with a network-wide event. "
        f"Gray bands are buckets where ≥8% of a 400-relay sample also dipped — "
        f"including 28 Jul, which {nickname} survived. Onionoo bucket math "
        f"lives in the #uptime info box, not here.",
    )
    save(fig, out_paths)


def uptime_onionoo_info(published, out_paths):
    """On-page info box + tooltip copy for Onionoo buckets and the two clocks."""
    fig, ax = plt.subplots(figsize=(11.2, 7.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(
        "#uptime information  ·  on the relay page, under the chart",
        loc="left", pad=10,
    )

    def box(y, h, color, title, body):
        ax.add_patch(FancyBboxPatch(
            (0.02, y), 0.96, h,
            boxstyle="square,pad=0",
            facecolor="#f8f9fa", edgecolor="#dddddd", linewidth=0.8,
        ))
        ax.add_patch(plt.Rectangle((0.02, y), 0.008, h, facecolor=color,
                                   edgecolor="none"))
        ax.text(0.05, y + h - 0.025, title, fontsize=10, fontweight="bold",
                color=NAVY, va="top")
        ax.text(0.05, y + h - 0.055, body, fontsize=8.2, color="#333333",
                va="top", linespacing=1.45, family="DejaVu Sans")

    box(
        0.62, 0.34, "#17a2b8",
        "Two uptime clocks",
        "Tor process uptime  —  descriptor last_restarted. How long this tor process\n"
        "has been running. You control this directly: restarts, crashes, host reboots,\n"
        "package upgrades. The page’s Current Status is this clock.\n"
        "\n"
        "Network-visible uptime  —  Onionoo /uptime Running. Whether directory\n"
        "authorities listed this relay as Running in each hourly consensus. You control\n"
        "this indirectly: ORPort, IPv6, firewall, hibernation, descriptor freshness.\n"
        "A consensus or authority event can also create a gap that is not your fault.\n"
        "The chart is this clock. The two will not match, and that is expected.",
    )
    box(
        0.22, 0.36, "#007bff",
        "How Onionoo packs the chart  (period-pill tooltip uses the first line)",
        "1M   each point is 4 hourly consensuses in a 4-hour window. Only 0 / 25 / 50 / 75 / 100%.\n"
        "6M   12-hour buckets (12 consensuses). More steps (e.g. 10/12 ≈ 83%).\n"
        "1Y   2-day buckets.   5Y   10-day buckets.   No 1-week graph — Onionoo removed it in 2020.\n"
        "\n"
        "Timestamps are interval midpoints: a point stamped 19 Jul 14:00 is 12:00–16:00 UTC.\n"
        "75% means the relay missed 1 of 4 hourly consensuses in that window — not “the\n"
        "process was 75% up.” A 5Y dip is a 10-day mix; it is coarser, not “more reliable.”\n"
        "\n"
        "Tooltip on 1M pill:  “1 month · 4-hour buckets · 4 hourly consensuses each”\n"
        "Tooltip on Overall Uptime:  “Network-visible Running, not process uptime.”",
    )
    box(
        0.04, 0.14, GRAY,
        "Network-wide gaps on the chart",
        "At build time, scan every relay’s 1_month Running series. For each 4-hour bucket,\n"
        "record the share of relays that were not 100%. If that share is ≥8% (about 2.5×\n"
        "the ~3% median), draw a gray band. This relay’s own dip inside that band is orange.",
    )
    caption(
        fig, published,
        "Same pattern as the flags-table “Bandwidth Values Explained” box. "
        "Keep the long Onionoo logic here (and in title= tooltips). Do not "
        "put the 0/25/50/75/100 table on the chart itself.",
    )
    save(fig, out_paths)


def load_uptime_periods(up_relay):
    out = {}
    block = up_relay.get("uptime") or {}
    for key in PERIOD_ORDER:
        ts, vals = history_series(block.get(key))
        if ts:
            out[key] = (ts, as_pct(vals))
    return out


def period_date_axis(ax, key):
    if key == "1_month":
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    elif key == "6_months":
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    elif key == "1_year":
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.xaxis.set_major_locator(mdates.YearLocator())


def plot_uptime_on_ax(ax, ts, pct, key, compact=False):
    arr = np.array(pct)
    ax.fill_between(ts, arr, 0, color=BLUE, alpha=0.16, linewidth=0)
    ax.plot(ts, pct, color=BLUE, linewidth=1.1 if compact else 1.6)
    below = arr < 98
    if below.any():
        ax.fill_between(
            ts, arr, 98, where=below, color=BAD, alpha=0.30, interpolate=True,
        )
    ax.axhline(98, color=ORANGE, linestyle="--", linewidth=0.9)
    lo = float(min(pct)) if pct else 0.0
    # Shared 0–100 for small multiples / long graphs. Zoom 1M/6M so 4h dips
    # stay visible when the month is a flat 99%.
    if compact or lo < 35 or key in ("1_year", "5_years"):
        ax.set_ylim(0, 106)
    else:
        ax.set_ylim(max(0.0, min(35.0, lo - 10.0)), 106)
    period_date_axis(ax, key)
    avg = float(np.mean(pct)) if len(pct) else 0.0
    if not compact:
        ax.axhline(avg, color=NAVY, linestyle=":", linewidth=1.0)
        ax.set_ylabel("Running (%)")
    else:
        ax.set_yticks([0, 50, 98, 100])
        ax.tick_params(labelsize=7)
    return avg


def draw_period_pills(fig, available_shorts, selected, left=0.08, bottom=0.905):
    """available_shorts / selected are 1M, 6M, 1Y, 5Y. Missing periods are omitted."""
    x = left
    for short in ("1M", "6M", "1Y", "5Y"):
        if short not in available_shorts:
            continue
        on = short == selected
        box = FancyBboxPatch(
            (x, bottom), 0.062, 0.036,
            boxstyle="round,pad=0.004,rounding_size=0.006",
            transform=fig.transFigure, clip_on=False,
            facecolor=NAVY if on else "white",
            edgecolor=NAVY, linewidth=1.1,
        )
        fig.add_artist(box)
        fig.text(
            x + 0.031, bottom + 0.018, short,
            transform=fig.transFigure, ha="center", va="center",
            fontsize=9, fontweight="bold",
            color="white" if on else NAVY,
        )
        x += 0.074
    missing = [s for s in ("1M", "6M", "1Y", "5Y") if s not in available_shorts]
    if missing:
        fig.text(
            x + 0.008, bottom + 0.018,
            "not published: " + ", ".join(missing),
            transform=fig.transFigure, ha="left", va="center",
            fontsize=8, color=GRAY,
        )


def _span_note(ts, key):
    days = (ts[-1] - ts[0]).days
    meta = PERIOD_META[key]
    if days + 20 < meta["nominal_days"]:
        return (
            f"series starts {ts[0].strftime('%-d %b %Y')} "
            f"(not a full {meta['title']})"
        )
    return ""


def uptime_periods_pills(periods, selected_key, nickname, published, question,
                         out_paths):
    meta = PERIOD_META[selected_key]
    ts, pct = periods[selected_key]
    fig = plt.figure(figsize=(11.2, 5.8))
    fig.subplots_adjust(bottom=0.18, top=0.80)
    available = [PERIOD_META[k]["short"] for k in PERIOD_ORDER if k in periods]
    draw_period_pills(fig, available, meta["short"])
    ax = fig.add_axes([0.08, 0.20, 0.90, 0.56])
    avg = plot_uptime_on_ax(ax, ts, pct, selected_key)
    extra = _span_note(ts, selected_key)
    title = (
        f"Uptime B  ·  {nickname}  ·  {meta['title']}  ·  "
        f"{meta['bucket']} buckets  ·  average {avg:.1f}%"
    )
    if extra:
        title += f"\n{extra}"
    ax.set_title(title)
    caption(fig, published, question)
    save(fig, out_paths)


def uptime_periods_multiples(periods, nickname, published, out_paths):
    keys = [k for k in PERIOD_ORDER if k in periods]
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 7.0))
    fig.subplots_adjust(bottom=0.12, top=0.90, hspace=0.38, wspace=0.22)
    fig.suptitle(f"Uptime periods — all published graphs   ·   {nickname}",
                 fontsize=13, fontweight="bold")
    for i, key in enumerate(PERIOD_ORDER):
        ax = axes[i // 2][i % 2]
        meta = PERIOD_META[key]
        if key not in periods:
            ax.set_axis_off()
            ax.text(
                0.5, 0.5,
                f"{meta['short']}  ·  not published\nOnionoo omitted this graph",
                ha="center", va="center", color=GRAY, fontsize=11,
                transform=ax.transAxes,
            )
            continue
        ts, pct = periods[key]
        avg = plot_uptime_on_ax(ax, ts, pct, key, compact=True)
        extra = _span_note(ts, key)
        ax.set_title(
            f"{meta['short']}  ·  {meta['bucket']} buckets  ·  {avg:.1f}%"
            + (f"\n{extra}" if extra else ""),
            fontsize=10,
        )
    caption(
        fig, published,
        "Question: how do 1M / 6M / 1Y / 5Y sit on one page when a relay has "
        "all four? Shared y-axis 0–100 so a 99% month and an 89% five-year "
        "are comparable. Empty cell = Onionoo omitted the graph, not 0%.",
    )
    save(fig, out_paths)


def uptime_periods_hero_sparks(periods, nickname, published, out_paths):
    hero_key = "1_month" if "1_month" in periods else next(iter(periods))
    others = [k for k in PERIOD_ORDER if k in periods and k != hero_key]
    fig = plt.figure(figsize=(11.2, 7.2))
    fig.subplots_adjust(bottom=0.10, top=0.90)
    fig.suptitle(f"Uptime periods — 1M hero + longer-period strip   ·   {nickname}",
                 fontsize=13, fontweight="bold")
    ax = fig.add_axes([0.08, 0.42, 0.90, 0.44])
    ts, pct = periods[hero_key]
    avg = plot_uptime_on_ax(ax, ts, pct, hero_key)
    meta = PERIOD_META[hero_key]
    ax.set_title(
        f"{meta['short']}  ·  {meta['bucket']} buckets  ·  average {avg:.1f}%"
    )
    if others:
        n = len(others)
        width = 0.90 / n
        for i, key in enumerate(others):
            a = fig.add_axes([0.08 + i * width, 0.14, width - 0.03, 0.20])
            ts, pct = periods[key]
            avg = plot_uptime_on_ax(a, ts, pct, key, compact=True)
            m = PERIOD_META[key]
            a.set_title(f"{m['short']}  ·  {m['bucket']}  ·  {avg:.1f}%", fontsize=9)
    caption(
        fig, published,
        "Question: can we see every published period without a click, without "
        "four full-height charts? 1M stays the large view (finest buckets, "
        "matches the health-row number). 6M / 1Y / 5Y are context. Omit a "
        "spark if Onionoo omitted the graph.",
    )
    save(fig, out_paths)


# ---------------------------------------------------------------------------
# Chart 6 — bandwidth (F3Netze, 1 month)
# ---------------------------------------------------------------------------

def event_x(when, x_values=None):
    """Map a datetime onto the axis. x_values None keeps a datetime axis."""
    if x_values is None:
        return when
    if len(x_values) < 2:
        return 0
    step = (x_values[1] - x_values[0]).total_seconds()
    if step <= 0:
        return 0
    return (when - x_values[0]).total_seconds() / step


def event_whens(ev):
    if ev.get("whens"):
        return list(ev["whens"])
    if ev.get("when") is not None:
        return [ev["when"]]
    return []


def restart_legend_label(whens):
    dates = ", ".join(w.strftime("%-d %b") for w in sorted(set(whens), reverse=True))
    return f"Last restarted  {dates}" if dates else "Last restarted"


def draw_event_lines(ax, events, x_values=None, lw=1.8):
    """Restart is a point on the time axis. Overload is not drawn here.

    Onionoo has no overload history graph — only a last-detected timestamp —
    so overload is a title / legend cue, not an x-axis range. Multiple
    restarts share one legend entry and get one vline each.
    """
    for ev in events:
        if ev["kind"] == "overload":
            continue
        for when in event_whens(ev):
            x = event_x(when, x_values)
            ax.axvline(x, color=ev["color"], linestyle=ev["ls"], linewidth=lw,
                       alpha=0.95, zorder=3)


def event_legend_handles(events):
    handles = []
    restart_whens = []
    restart_style = None
    for ev in events:
        if ev["kind"] == "overload":
            continue
        if ev["kind"] == "restart":
            restart_whens.extend(event_whens(ev))
            restart_style = ev
            continue
        handles.append(Line2D(
            [0], [0], color=ev["color"], linestyle=ev["ls"], linewidth=1.8,
            label=ev["legend"],
        ))
    if restart_whens and restart_style:
        handles.append(Line2D(
            [0], [0], color=restart_style["color"],
            linestyle=restart_style["ls"], linewidth=1.8,
            label=restart_legend_label(restart_whens),
        ))
    return handles


def pad_xlim(ax, ts, x_values=None):
    """Pad the series; do not extend the axis for inferred overload."""
    if not ts:
        return
    if x_values is None:
        xmin, xmax = ts[0], ts[-1]
        pad = (xmax - xmin) * 0.03
        ax.set_xlim(xmin, xmax + pad)
        return
    ax.set_xlim(-1, float(len(ts) - 1) + 0.6)


def overload_now_status(relay, published):
    """Thin wrapper: parse Onionoo published time, then current_overload_status."""
    if isinstance(published, str):
        try:
            now_ts = parse_onionoo_ts(published).timestamp()
        except (TypeError, ValueError):
            now_ts = None
    elif published is not None:
        now_ts = published.timestamp()
    else:
        now_ts = None
    return current_overload_status(relay, now_ts)


def overload_quiet_text(status):
    """Quieter than the old OVERLOADED NOW pill. None if not current."""
    if not status:
        return None
    if status.get("last_report"):
        when = status["last_report"].strftime("%-d %b %H:%M") + " UTC"
        return f"currently overloaded · last report {when}"
    return "currently overloaded"


def throughput_legend_handles(advertised_mbit, events, overload_status=None,
                              overload_in_legend=False):
    handles = [
        Line2D([0], [0], color=WRITE, linewidth=1.8, label="Write (outbound)"),
        Line2D([0], [0], color=BLUE, linewidth=1.8, label="Read (inbound)"),
    ]
    if advertised_mbit:
        handles.append(Line2D(
            [0], [0], color=ORANGE, linestyle="--", linewidth=1.4,
            label=f"Advertised  {advertised_mbit:.0f} Mbit/s",
        ))
    handles.extend(event_legend_handles(events))
    if overload_in_legend and overload_status:
        handles.append(Line2D(
            [0], [0], color=OVERLOAD, marker="D", linestyle="None",
            markersize=6, label=overload_quiet_text(overload_status),
        ))
    return handles


LEGEND_FONTSIZE = 8.0


def place_legend_above_axes(ax, handles, fontsize=None, ncol=None,
                            wrap_last=False):
    """Legend in the empty band above advertised / data_max.

    ylim reserves that band (see throughput_ylim). Do not use loc=upper
    left on a tight ylim — that is what sat the legend on the series.

    Overload wraps onto a second line, but it must be a *separate*
    legend. Putting it in the same ncol grid parks the long
    “currently overloaded · last report …” label in Write’s column
    and opens a huge gap before Read.
    """
    if not handles:
        return
    style = dict(
        fontsize=LEGEND_FONTSIZE if fontsize is None else fontsize,
        frameon=True,
        fancybox=False,
        edgecolor="#eeeeee",
        facecolor="white",
        framealpha=0.96,
        borderaxespad=0.25,
        columnspacing=1.0,
        handlelength=1.6,
        handletextpad=0.4,
        labelspacing=0.15,
    )
    if wrap_last and len(handles) > 1:
        first = ax.legend(
            handles=handles[:-1], loc="upper left",
            ncol=len(handles) - 1, **style,
        )
        ax.add_artist(first)
        fig = ax.figure
        fig.canvas.draw()
        bbox = first.get_window_extent(fig.canvas.get_renderer())
        (x0, y0), _ = ax.transAxes.inverted().transform(
            [[bbox.x0, bbox.y0], [bbox.x1, bbox.y1]]
        )
        second = dict(style)
        second["frameon"] = False
        second["borderaxespad"] = 0.0
        ax.legend(
            handles=handles[-1:], loc="upper left",
            bbox_to_anchor=(x0, y0 - 0.006), bbox_transform=ax.transAxes,
            **second,
        )
        return
    if ncol is None:
        ncol = min(len(handles), 4)
    ax.legend(handles=handles, loc="upper left", ncol=ncol, **style)


def place_legend_below_axes(ax, handles, wrap_last=False, gap_pt=8.0,
                            fontsize=8.5):
    """Same attachment as the write/read key: just under this panel.

    Used when both legends sit under their axes so the page has one
    pattern, not “throughput key on the series, ratio key under the
    dates.”
    """
    if not handles:
        return None
    axes_h_in = ax.get_position().height * ax.figure.get_figheight()
    offset = gap_pt / 72.0 / max(axes_h_in, 0.05)
    style = dict(
        fontsize=fontsize,
        frameon=True,
        fancybox=False,
        edgecolor="#eeeeee",
        facecolor="white",
        framealpha=0.96,
        borderaxespad=0.0,
        borderpad=0.25,
        columnspacing=1.0,
        handlelength=1.6,
        handletextpad=0.4,
        labelspacing=0.15,
    )
    if wrap_last and len(handles) > 1:
        first = ax.legend(
            handles=handles[:-1], loc="upper left",
            bbox_to_anchor=(0.0, -offset), ncol=len(handles) - 1, **style,
        )
        ax.add_artist(first)
        fig = ax.figure
        fig.canvas.draw()
        bbox = first.get_window_extent(fig.canvas.get_renderer())
        (x0, y0), _ = ax.transAxes.inverted().transform(
            [[bbox.x0, bbox.y0], [bbox.x1, bbox.y1]]
        )
        second = dict(style)
        second["frameon"] = False
        return ax.legend(
            handles=handles[-1:], loc="upper left",
            bbox_to_anchor=(x0, y0 - 0.012), bbox_transform=ax.transAxes,
            **second,
        )
    ncol = min(len(handles), 4)
    return ax.legend(
        handles=handles, loc="upper left",
        bbox_to_anchor=(0.0, -offset), ncol=ncol, **style,
    )


THROUGHPUT_TITLE_PAD = 10
# Same pad as throughput so the two stacked headers line up. The
# write/read legend sits *below* the strip, not under the title.
RATIO_TITLE_PAD = THROUGHPUT_TITLE_PAD


def throughput_title_loc(overload_status, overload_mode):
    """Same loc on both stacked titles so the headers line up."""
    if overload_mode == "title" and overload_status:
        return "left"
    return "center"


def apply_throughput_title(ax, title, overload_status, overload_mode,
                          loc=None, pad=None):
    """overload_mode: title | legend | none."""
    if not title:
        return
    pad = THROUGHPUT_TITLE_PAD if pad is None else pad
    loc = loc or throughput_title_loc(overload_status, overload_mode)
    if loc == "left":
        ax.set_title(title, loc="left", pad=pad)
        if overload_mode == "title" and overload_status:
            ax.set_title(
                overload_quiet_text(overload_status),
                loc="right", pad=pad, color=OVERLOAD,
                fontsize=9, fontweight="normal",
            )
        return
    ax.set_title(title, pad=pad)


def throughput_ylim(ax, read_m, write_m, advertised_mbit, legend_rows=1,
                   tight=False):
    """Leave a legend shelf above advertised (or data, if higher).

    tight=True when the key sits under the panel — no empty band.
    """
    data_max = max(list(write_m) + list(read_m) + [0.0])
    ceiling = max(advertised_mbit or 0.0, data_max) or 1.0
    if tight:
        extra = 1.10
    else:
        # One compact two-row box needs less shelf than the old stacked
        # legends (1.42). Keep a little more than a single row so the
        # diamond does not sit on the advertised line.
        extra = 1.28 if legend_rows >= 2 else 1.26
    ax.set_ylim(0, ceiling * extra)


def role_of(flags):
    flags = flags or []
    exit_f = "Exit" in flags
    guard_f = "Guard" in flags
    if exit_f and guard_f:
        return "Exit+Guard"
    if exit_f:
        return "Exit"
    if guard_f:
        return "Guard"
    return "Middle"


def load_role_bands():
    raw = json.loads(ROLE_BANDS_PATH.read_text())
    return raw


def bands_for_flags(flags, catalog=None):
    """Frozen typical / uncommon / investigate for this relay's flag set."""
    catalog = catalog or load_role_bands()
    role = role_of(flags)
    row = (catalog.get("roles") or {}).get(role)
    if not row:
        return {
            "role": role,
            "typical_lo": RATIO_LO,
            "typical_hi": RATIO_HI,
            "invest_lo": RATIO_INVESTIGATE_LO,
            "invest_hi": RATIO_INVESTIGATE_HI,
            "n": 0,
        }
    return {"role": role, **row}


def ratio_zone_phrase(mean_ratio, bands=None):
    bands = bands or {
        "typical_lo": RATIO_LO, "typical_hi": RATIO_HI,
        "invest_lo": RATIO_INVESTIGATE_LO, "invest_hi": RATIO_INVESTIGATE_HI,
        "role": "all",
    }
    role = bands.get("role") or "this role"
    tlo, thi = bands["typical_lo"], bands["typical_hi"]
    ilo, ihi = bands["invest_lo"], bands["invest_hi"]
    if tlo <= mean_ratio <= thi:
        return (f"inside {role} typical {tlo:.2f}–{thi:.2f} "
                f"(this role's p10–p90)")
    if ilo <= mean_ratio <= ihi:
        return (f"uncommon for {role} at {mean_ratio:.2f} "
                f"(outside p10–p90, inside p2–p98)")
    return (f"investigate for {role} at {mean_ratio:.2f} "
            f"(beyond this role's p98)")


def load_ratio_overlays():
    path = Path(__file__).resolve().parent / "data" / "ratio_overlays.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())

    def as_series(rows):
        return {parse_onionoo_ts(t): v for t, v, _n in rows}

    return {
        "role": as_series(raw.get("exitguard_daily") or []),
        "role_label": "Peers (network median)",
        "operator": as_series(raw.get("family_daily") or []),
        "operator_label": "Operator Family (median, n=24)",
        "family_outliers": raw.get("family_outliers", 0),
        "family_n": raw.get("family_n", 0),
    }


def overlay_values(ts, series):
    if not series:
        return None
    return [series.get(t, np.nan) for t in ts]


# Locked: judgment + numeric range + percentile. Role lives on the
# chart title; census n is a footnote. See band_legend_labels().
DEFAULT_BAND_COPY = "range_pct"
BAND_COPY_STYLES = (
    "current",
    "full",
    "range_pct",
    "range_only",
    "header",
)
BAND_COPY_META = {
    "current": {
        "short": "Current",
        "title": "Current — uneven slots",
        "blurb": (
            "Typical carries range + role + percentile + n. Uncommon is "
            "two ranges only. Investigate has range + role + a different "
            "percentile phrase, and no n."
        ),
    },
    "full": {
        "short": "1 · Fill every slot",
        "title": "Proposal 1 — fill every slot",
        "blurb": (
            "Same four fields on every row: range, role, percentile, n. "
            "Uncommon gets p2–p10 / p90–p98. n is the same census on all "
            "three (redundant, but parallel)."
        ),
    },
    "range_pct": {
        "short": "2 · Range + percentile",
        "title": "Proposal 2 — range + percentile",
        "blurb": (
            "Chosen. Judgment + numeric range + percentile on every "
            "swatch. Role is on the chart title. Census n is the "
            "footnote. Investigate uses <p2 or >p98 for the two-sided tail."
        ),
    },
    "range_only": {
        "short": "3 · Name + range",
        "title": "Proposal 3 — name + range",
        "blurb": (
            "Only the judgment word and the numbers. Percentiles stay on "
            "the y-axis (p10–p90, >p98). Uncommon uses “or” like "
            "Investigate, not a slash."
        ),
    },
    "header": {
        "short": "4 · Shared role header",
        "title": "Proposal 4 — shared role header",
        "blurb": (
            "Role and n sit on one header line. The three bands then "
            "share the same two fields: range + percentile."
        ),
    },
}


def bands_role(bands):
    return (bands or {}).get("role") or ""


def with_role(title, bands):
    """Put the flag-set role on the title so the legend does not repeat it."""
    role = bands_role(bands)
    if not title or not role or role in title:
        return title
    return f"{title}  ·  {role}"



# Contact `url:` host, optional scheme. Same token Allium uses for AROI.
_RE_URL_FIELD = re.compile(r"\burl:(?:https?://)?([^,\s/]+)", re.I)


def operator_from_contact(contact):
    """Short operator label for the chart identity.

    AROI / `url:` host only. Omit when missing — do not dump the raw
    contact, an email, or `as_name` (that is usually the host, not the
    operator).
    """
    if not contact:
        return ""
    match = _RE_URL_FIELD.search(contact)
    if not match:
        return ""
    host = match.group(1).strip().lower()
    if host.startswith("www."):
        host = host[4:]
    host = host.split("/")[0]
    if "." not in host or host in ("none", "localhost"):
        return ""
    return host


def chart_identity(nickname, operator=None):
    """`jeangrae · 1aeo.com`, or just the nickname when there is no AROI."""
    nick = (nickname or "").strip()
    op = (operator or "").strip()
    if op and nick and op.lower() != nick.lower():
        return f"{nick}  ·  {op}"
    return nick or op


# Tied with axes.titlesize (13 pt bold). Largest type on the figure,
# without overshooting the page h1.
IDENTITY_FONTSIZE = 13
# Clear air between the identity baseline box and the Throughput title.
# The old 5 pt offset sat on top of the 13 pt title.
IDENTITY_TITLE_GAP_PT = 12
IDENTITY_EXTRA_FIG_H = 0.48
IDENTITY_TOP_SHIFT = 0.075
IDENTITY_TITLE_PAD_BOOST = 6


def apply_chart_identity(ax, identity, loc="left", title_pad=None):
    """Names above the metric title, same 13 pt bold as Throughput.

    Offset is measured from the rendered title so the two lines cannot
    collide. Falls back to pad + title size + gap if the title is empty.
    Identity is never drawn on the write/read strip.
    """
    if not identity:
        return
    pad = THROUGHPUT_TITLE_PAD if title_pad is None else title_pad
    ha = "left" if loc == "left" else "center"
    x = 0.0 if loc == "left" else 0.5
    fig = ax.figure
    fig.canvas.draw()
    title = ax.title
    if title is not None and title.get_text():
        renderer = fig.canvas.get_renderer()
        title_top_px = title.get_window_extent(renderer).y1
        axes_top_px = ax.transAxes.transform((0.0, 1.0))[1]
        offset_in = (
            (title_top_px - axes_top_px) / fig.dpi
            + IDENTITY_TITLE_GAP_PT / 72.0
        )
    else:
        offset_in = (
            pad + IDENTITY_FONTSIZE + IDENTITY_TITLE_GAP_PT
        ) / 72.0
    ax.text(
        x, 1.0, identity,
        transform=ax.transAxes + ScaledTranslation(
            0, offset_in, fig.dpi_scale_trans,
        ),
        ha=ha, va="bottom",
        fontsize=IDENTITY_FONTSIZE, fontweight="bold", color=NAVY,
        clip_on=False,
    )


def sibling_ratio_title(throughput_title, bands=None):
    """Keep the write/read title in lockstep with the throughput title.

    Identity lives above the stacked figure, not in this string.
    `Throughput · last 30 days · Guard` becomes
    `Write / read · last 30 days · Guard`. An empty throughput title
    (rejected hero option) stays empty on the strip. If a comparison
    mockup prefixes the identity in front of Throughput, drop that
    prefix here — the write/read panel is not the overall chart.
    """
    if throughput_title is None:
        return with_role("Write / read", bands)
    if not throughput_title:
        return ""
    metric = throughput_title.split("\n")[-1]
    idx = metric.find("Throughput")
    if idx >= 0:
        return "Write / read" + metric[idx + len("Throughput"):]
    return with_role("Write / read", bands)


def apply_ratio_title(ax, title, loc="center", fontsize=None, pad=None):
    if not title:
        return
    kwargs = {"pad": RATIO_TITLE_PAD if pad is None else pad, "loc": loc}
    if fontsize is not None:
        kwargs["fontsize"] = fontsize
    ax.set_title(title, **kwargs)


# Light-theme chrome borrowed from 1aeo-blog-charts: hide top/right spines,
# y-grid only, left titles, a method subtitle, series-weight hierarchy, and
# at most one programmatic callout. Keep Okabe–Ito. Do not use the blog
# dark surface or #00ff7f on every relay page.
CHROME_STYLE_ORDER = ("despine", "left_title", "weights", "subtitle", "callout")
CHROME_STYLES = {
    "despine": {
        "id": "1",
        "name": "Despine + y-grid",
        "blurb": (
            "Smallest change. Hide the top and right spines and keep only "
            "the y-grid. Titles stay centered. Line weights stay equal. "
            "Shows how much of the “boxed matplotlib” look is just chrome."
        ),
        "spines": "left_bottom",
        "grid": "y",
        "title_loc": "center",
        "weights": "flat",
        "subtitle": False,
        "callout": False,
    },
    "left_title": {
        "id": "2",
        "name": "Left titles",
        "blurb": (
            "Style 1 plus left-aligned titles on both strips. Matches the "
            "blog header alignment without a narrative headline. Overload "
            "still uses the title-right cue when that mode is on."
        ),
        "spines": "left_bottom",
        "grid": "y",
        "title_loc": "left",
        "weights": "flat",
        "subtitle": False,
        "callout": False,
    },
    "weights": {
        "id": "3",
        "name": "Series weights",
        "blurb": (
            "Style 2 plus a weight hierarchy: write / this-relay heaviest, "
            "read a step down, advertised and overlays thinner. The eye "
            "hits the operator’s series first."
        ),
        "spines": "left_bottom",
        "grid": "y",
        "title_loc": "left",
        "weights": "hierarchy",
        "subtitle": False,
        "callout": False,
    },
    "subtitle": {
        "id": "4",
        "name": "Method subtitle",
        "blurb": (
            "Style 3 plus a gray method line under each title: Onionoo "
            "bucket on throughput, frozen-band rule on write/read. Method, "
            "not a story. Census n stays the footnote."
        ),
        "spines": "left_bottom",
        "grid": "y",
        "title_loc": "left",
        "weights": "hierarchy",
        "subtitle": True,
        "callout": False,
    },
    "callout": {
        "id": "5",
        "name": "Recommended — one auto-callout",
        "blurb": (
            "Ship this. Style 4 plus one programmatic callout when a day "
            "is beyond this role’s p98. Built from the series (date, "
            "ratio). No callout when the strip is typical. Still light, "
            "still Okabe–Ito. No hand-placed arrows, no neon green."
        ),
        "spines": "left_bottom",
        "grid": "y",
        "title_loc": "left",
        "weights": "hierarchy",
        "subtitle": True,
        "callout": True,
        "recommend": True,
    },
}
CHROME_WEIGHTS = {
    "flat": {
        "write": 1.8, "read": 1.8, "advertised": 1.4, "restart": 1.8,
        "relay": 1.7, "family": 1.6, "peers": 1.4, "investigate": 2.0,
    },
    "hierarchy": {
        "write": 2.35, "read": 1.65, "advertised": 1.15, "restart": 1.25,
        "relay": 2.15, "family": 1.25, "peers": 1.25, "investigate": 2.3,
    },
}
SUBTITLE_TITLE_PAD = 22


def chrome_spec(name):
    return CHROME_STYLES[name]


def chrome_weights(chrome):
    key = (chrome or {}).get("weights") or "flat"
    return dict(CHROME_WEIGHTS.get(key) or CHROME_WEIGHTS["flat"])


def chrome_title_loc(chrome, overload_status, overload_mode):
    if overload_mode == "title" and overload_status:
        return "left"
    if chrome and chrome.get("title_loc"):
        return chrome["title_loc"]
    return throughput_title_loc(overload_status, overload_mode)


def apply_chrome_axes(ax, chrome):
    if not chrome:
        return
    if chrome.get("spines") == "left_bottom":
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#bbbbbb")
        ax.spines["bottom"].set_color("#bbbbbb")
    if chrome.get("grid") == "y":
        ax.grid(True, axis="y")
        ax.xaxis.grid(False)
        ax.set_axisbelow(True)
    ax.tick_params(colors="#555555")


def apply_method_subtitle(ax, text):
    if not text:
        return
    ax.text(
        0.0, 1.028, text, transform=ax.transAxes, ha="left", va="bottom",
        fontsize=8.0, color="#6B7280",
    )


def throughput_method_subtitle(period_key="1_month"):
    meta = BW_PERIOD_META.get(period_key) or BW_PERIOD_META["1_month"]
    return (
        f"Onionoo write/read_history · {meta['bucket']} buckets · "
        f"advertised is the current descriptor, not a history"
    )


def ratio_method_subtitle(bands):
    return (
        "Frozen quiet-census bands · typical is this flag set’s p10–p90 · "
        "investigate is beyond p98"
    )


def peers_word(bands):
    """Operator-facing plural for this flag set. Not 'flag set' or 'role'."""
    role = bands_role(bands) or "relays"
    return {
        "Guard": "Guards",
        "Exit": "Exits",
        "Exit+Guard": "Exit+Guards",
        "Middle": "middle relays",
    }.get(role, role)


def throughput_subtitle_text(period_key="1_month", style=None):
    """style: None/jargon | peers | plain | baseline | none."""
    if style in (None, "jargon"):
        return throughput_method_subtitle(period_key)
    if style == "peers":
        return (
            "Daily write and read · dashed line is today’s advertised bandwidth"
        )
    if style == "plain":
        return (
            "Each point is one day · advertised is the current limit, "
            "not a history"
        )
    if style == "baseline":
        return "Daily totals · advertised is today’s descriptor, not a history"
    return ""


def ratio_subtitle_text(bands, style=None):
    """style: None/jargon | peers | plain | baseline | none."""
    if style in (None, "jargon"):
        return ratio_method_subtitle(bands)
    peers = peers_word(bands)
    if style == "peers":
        return (
            f"Compared with other {peers} · typical is the middle 80% · "
            f"investigate is the tails"
        )
    if style == "plain":
        return f"Green is usual for {peers} · red is rare for {peers}"
    if style == "baseline":
        return f"Vs other {peers} · fixed baseline, not this week’s ranking"
    return ""


OUTCOME_STYLES = ("dated", "verdict", "who")


def _role_article(role):
    if not role:
        return "a relay"
    if role[0].lower() in "aeiou":
        return f"an {role}"
    return f"a {role}"


def _n_day_runs(dates):
    dates = sorted(dates)
    if not dates:
        return 0
    n = 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days > 1:
            n += 1
    return n


def _format_day_span(dates):
    dates = sorted(dates)
    if not dates:
        return ""
    if len(dates) == 1:
        return dates[0].strftime("%-d %b")
    consec = all((dates[i] - dates[i - 1]).days == 1 for i in range(1, len(dates)))
    if consec:
        return f"{dates[0].strftime('%-d')}–{dates[-1].strftime('%-d %b')}"
    return ", ".join(d.strftime("%-d %b") for d in dates)


def _overlay_left_typical(ts, series, bands, day_set):
    """True if the overlay is outside typical on most of those days."""
    if not series or not day_set:
        return None
    vals = overlay_values(ts, series)
    if vals is None:
        return None
    tlo, thi = bands["typical_lo"], bands["typical_hi"]
    hits = []
    for t, v in zip(ts, vals):
        if t.date() not in day_set:
            continue
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        hits.append(v < tlo or v > thi)
    if not hits:
        return None
    return sum(hits) >= max(1, (len(hits) + 1) // 2)


def summarize_bandwidth_outcome(ts, write_m, read_m, advertised_mbit, events,
                                overlays, bands, overload_status):
    """What the two strips conclude. Used by outcome subtitles."""
    bands = bands or {}
    overlays = overlays or {}
    tlo = bands.get("typical_lo", RATIO_LO)
    thi = bands.get("typical_hi", RATIO_HI)
    ilo = bands.get("invest_lo", RATIO_INVESTIGATE_LO)
    ihi = bands.get("invest_hi", RATIO_INVESTIGATE_HI)
    role = bands_role(bands) or "relay"
    rows = []
    for t, w, r in zip(ts or [], write_m or [], read_m or []):
        if not r:
            continue
        rows.append((t, w, r, w / r))
    if len(rows) < 3:
        return {
            "enough": False, "role": role, "overloaded": bool(overload_status),
        }
    mean_ratio = float(np.mean([row[3] for row in rows]))
    mean_write = float(np.mean([row[1] for row in rows]))
    mean_read = float(np.mean([row[2] for row in rows]))
    if tlo <= mean_ratio <= thi:
        zone = "typical"
    elif ilo <= mean_ratio <= ihi:
        zone = "uncommon"
    else:
        zone = "investigate"
    invest = [row for row in rows if row[3] < ilo or row[3] > ihi]
    off = [row for row in rows if row[3] > 1.70]
    write_heavy = [row for row in invest if row[3] > thi]
    read_heavy = [row for row in invest if row[3] < tlo]
    day_set = {row[0].date() for row in invest}
    family_left = _overlay_left_typical(
        ts, overlays.get("operator"), bands, day_set,
    )
    role_left = _overlay_left_typical(
        ts, overlays.get("role"), bands, day_set,
    )
    if not invest:
        who = "with_peers"
    elif role_left:
        who = "role"
    elif family_left:
        who = "family"
    else:
        who = "relay"
    util = (100.0 * mean_write / advertised_mbit) if advertised_mbit else None
    if write_heavy and len(write_heavy) >= len(read_heavy):
        spike = "write"
    elif read_heavy:
        spike = "read"
    else:
        spike = None
    persistent = zone == "investigate" and len(invest) >= max(5, len(rows) // 3)
    ev = events_in_span(events, ts)
    restarts = []
    for item in ev:
        if item.get("kind") == "restart":
            restarts.extend(item.get("whens") or [])
    if util is None:
        thru = "unknown"
    elif spike and not persistent:
        thru = "spike"
    elif mean_write < 20 and mean_read < 20:
        thru = "crash"
    elif util >= 70:
        thru = "near"
    elif util < 25:
        thru = "low"
    else:
        thru = "steady"
    return {
        "enough": True,
        "role": role,
        "zone": zone,
        "mean_ratio": mean_ratio,
        "mean_write": mean_write,
        "mean_read": mean_read,
        "advertised": advertised_mbit,
        "util": util,
        "invest": invest,
        "off": off,
        "who": who,
        "family_left": family_left,
        "role_left": role_left,
        "spike": spike,
        "persistent": persistent,
        "thru": thru,
        "overloaded": bool(overload_status),
        "restarts": restarts,
    }


def _util_clause(outcome):
    """Raw write next to % of advertised. Never % alone."""
    write = outcome.get("mean_write")
    util = outcome.get("util")
    if write is None:
        return ""
    if util is not None:
        return f"{write:.0f} Mbit/s ({util:.0f}% of advertised)"
    return f"{write:.0f} Mbit/s"


def _is_all_clear(outcome):
    """Nothing to say: typical strip, no spike, no crash."""
    if not outcome or not outcome.get("enough"):
        return False
    return (
        outcome["thru"] not in ("spike", "crash")
        and not outcome["invest"]
        and outcome["zone"] == "typical"
    )


def format_outcome_subtitle(outcome, which, style):
    """which: throughput | ratio. style: dated | verdict | who.

    Who (ship this): empty when history is thin or the month is all-clear.
    No “this relay” — identity sits above Throughput. No “still with.”
    No “moved” — a write/read spike says spiked (bad); both-fell says
    dropped (bad). Investigate / off-band says Outside the band, not Left.
    Uncommon / no-investigate puts the live write/read mean on the same
    line as inside the {role} band with other {peers}. Quiet typical
    stays empty — do not invent “inside the band.”
    Any advertised share is `N Mbit/s (P% of advertised)`.
    """
    if not outcome or not outcome.get("enough"):
        return ""
    if style == "who" and _is_all_clear(outcome):
        return ""
    role = outcome["role"]
    art = _role_article(role)
    zone = outcome["zone"]
    n_inv = len(outcome["invest"])
    n_off = len(outcome["off"])
    span = _format_day_span([row[0].date() for row in outcome["invest"]])
    ratios = " / ".join(f"{row[3]:.2f}" for row in outcome["off"][:3])
    if not ratios and outcome["invest"]:
        ratios = " / ".join(f"{row[3]:.2f}" for row in outcome["invest"][:3])
    util = outcome.get("util")
    write = outcome["mean_write"]
    adv = outcome.get("advertised")
    ov = outcome["overloaded"]
    ov_bit = " · currently overloaded" if ov else ""
    util_bit = _util_clause(outcome)

    if which == "throughput":
        if style == "dated":
            if outcome["thru"] == "spike" and span:
                kind = "Write" if outcome["spike"] == "write" else "Read"
                body = f"{kind} jumped {span}"
            elif outcome["thru"] == "crash":
                body = "Write and read both dropped"
            elif util_bit:
                body = util_bit
            else:
                body = f"Month-mean write {write:.0f} Mbit/s"
            if outcome["thru"] == "spike" and util_bit:
                body += f" · {util_bit}"
            return body + ov_bit
        if style == "verdict":
            if outcome["thru"] == "spike":
                n = _n_day_runs([row[0].date() for row in outcome["invest"]]) or 1
                kind = "write" if outcome["spike"] == "write" else "read"
                body = f"{n} {kind} spike{'' if n == 1 else 's'} · the rest of the month is quiet"
            elif outcome["thru"] == "crash":
                body = "Throughput crashed · write and read both fell"
            elif outcome["thru"] == "near":
                body = "Delivering most of advertised"
            elif outcome["thru"] == "low":
                body = "Steady · well below advertised"
            else:
                body = "Steady throughput"
            if util_bit and outcome["thru"] in ("near", "low", "steady", "crash"):
                body += f" · {util_bit}"
            return body + ov_bit
        # who
        if outcome["thru"] == "spike":
            kind = "Write" if outcome["spike"] == "write" else "Read"
            body = f"{kind} spiked"
            if util_bit:
                body += f" · {util_bit}"
            return body
        if outcome["thru"] == "crash":
            body = "Write and read both dropped"
            if util_bit:
                body += f" · {util_bit}"
            return body
        return util_bit

    # ratio
    if style == "dated":
        if n_off:
            return (
                f"{n_off} day{'s' if n_off != 1 else ''} off the 1.70 scale "
                f"({ratios}) · month-mean {outcome['mean_ratio']:.2f}, "
                f"{zone} for {art}"
            )
        if n_inv:
            return (
                f"{n_inv} investigate day{'s' if n_inv != 1 else ''} "
                f"{span} · month-mean {outcome['mean_ratio']:.2f}, "
                f"{zone} for {art}"
            )
        return (
            f"Month-mean write/read {outcome['mean_ratio']:.2f} · "
            f"{zone} for {art}"
        )
    if style == "verdict":
        if n_off or n_inv:
            n = n_off or n_inv
            return (
                f"{n} investigate day{'s' if n != 1 else ''} · "
                f"the rest {('typical' if zone == 'typical' else zone)}"
            )
        if zone == "typical":
            return "Typical all month"
        if zone == "uncommon":
            return f"Uncommon for {art} · no investigate day"
        return f"Investigate for {art} · the whole month"
    # who
    peers = peers_word({"role": role})
    if outcome["who"] == "role":
        return (
            "Outside the band with other " + peers
            + (f" {span}" if span else "")
        )
    if outcome["who"] == "family":
        return (
            f"Outside the {role} band with the family · "
            f"other {peers} stayed"
        )
    if outcome["who"] == "relay" and (n_off or n_inv or outcome["persistent"]):
        # Persistent is the whole month off-band — skip the date list.
        date_bit = "" if outcome["persistent"] else (f" {span}" if span else "")
        return (
            f"Outside the {role} band"
            + date_bit
            + " · family and peers stayed"
        )
    if not outcome["invest"] and zone == "typical":
        return ""
    return (
        f"Write/read {outcome['mean_ratio']:.2f} · "
        f"inside the {role} band with other {peers}"
    )


def auto_spike_callout(ax, ts, write_m, read_m, bands):
    """One annotation on the worst investigate day. Skip if none."""
    if not ts:
        return False
    ihi = (bands or {}).get("invest_hi", RATIO_INVESTIGATE_HI)
    rows = []
    for t, w, r in zip(ts, write_m, read_m):
        if not r:
            continue
        ratio = w / r
        if ratio > ihi:
            rows.append((ratio, t, w, r))
    if not rows:
        return False
    peak = max(rows, key=lambda row: row[0])
    peak_t = peak[1]
    run = [peak]
    by_day = {row[1].date(): row for row in rows}
    day = peak_t.date()
    prev = day - timedelta(days=1)
    nxt = day + timedelta(days=1)
    if prev in by_day:
        run.append(by_day[prev])
    if nxt in by_day:
        run.append(by_day[nxt])
    run.sort(key=lambda row: row[1])
    scale_bit = (
        "off the 1.70 scale" if peak[0] > 1.70 else "beyond this role’s p98"
    )
    if len(run) == 1:
        label = (
            f"{peak_t.strftime('%-d %b')} · write/read {peak[0]:.2f} · "
            f"{scale_bit}"
        )
    else:
        ratios = " / ".join(f"{row[0]:.2f}" for row in run)
        label = (
            f"{run[0][1].strftime('%-d')}–{run[-1][1].strftime('%-d %b')} · "
            f"write/read {ratios} · {scale_bit}"
        )
    span = (ts[-1] - ts[0]).total_seconds()
    frac = ((peak_t - ts[0]).total_seconds() / span) if span else 0.0
    if frac > 0.62:
        xytext, ha = (-14, 16), "right"
    else:
        xytext, ha = (14, 16), "left"
    ax.annotate(
        label,
        xy=(peak_t, peak[2]),
        xytext=xytext,
        textcoords="offset points",
        fontsize=8.0,
        color=NAVY,
        fontweight="bold",
        ha=ha,
        va="bottom",
        arrowprops=dict(arrowstyle="-", color=GRAY, lw=0.8),
        bbox=dict(
            boxstyle="round,pad=0.28", fc="white", ec="#dddddd", alpha=0.94,
        ),
        zorder=6,
    )
    return True


def _ratio_legend_style():
    """Same type size as the throughput key. Do not go smaller."""
    return dict(
        fontsize=LEGEND_FONTSIZE,
        frameon=True,
        fancybox=False,
        edgecolor="#eeeeee",
        facecolor="white",
        framealpha=0.96,
        borderaxespad=0.0,
        borderpad=0.25,
        columnspacing=0.85,
        handlelength=1.6,
        handletextpad=0.4,
        labelspacing=0.18,
    )


def _split_ratio_handles(handles):
    series = [h for h in handles if not isinstance(h, Patch)]
    bands = [h for h in handles if isinstance(h, Patch)]
    return series, bands


def place_ratio_legend_right(ax, handles):
    """Legend to the right of the axes. Used when two strips are stacked
    (band-copy): a below-legend on the top strip lands on the bottom one.
    """
    if not handles:
        return
    ax.legend(
        handles=handles, loc="center left",
        bbox_to_anchor=(1.02, 0.5), ncol=1, **_ratio_legend_style(),
    )


def _row_major_ratio_handles(series, bands):
    """Interleave so ncol=len(series) paints series on row 1, bands on row 2.

    Matplotlib fills a legend grid by column.
    """
    n = max(len(series), len(bands), 1)
    out = []
    for i in range(n):
        if i < len(series):
            out.append(series[i])
        if i < len(bands):
            out.append(bands[i])
    return out


def place_ratio_legend_below(ax, handles, gap_pt=16.0):
    """Legend just under the date labels, never on the series or the bands.

    loc=upper right inside the axes sat the box on the colored bands
    and on off-scale markers (jeangrae 22–23 Jul triangles). One box,
    series on the first row and band swatches on the second. Convert the
    point gap to this axes' height — a mixed ScaledTranslation is ignored
    as a legend bbox_transform, and a fixed -0.32 fraction is far too
    much on a short write/read strip.
    """
    if not handles:
        return None
    series, bands = _split_ratio_handles(handles)
    ax.tick_params(axis="x", pad=2, labelbottom=True)
    axes_h_in = ax.get_position().height * ax.figure.get_figheight()
    offset = gap_pt / 72.0 / max(axes_h_in, 0.05)
    return ax.legend(
        handles=_row_major_ratio_handles(series, bands),
        loc="upper left",
        bbox_to_anchor=(0.0, -offset),
        ncol=max(len(series), 1),
        **_ratio_legend_style(),
    )


def place_ratio_legend_shelf(ax, handles):
    """Legend in a reserved white band above 1.70. Same 'key at the
    top of the panel' pattern as the throughput shelf.
    """
    if not handles:
        return None
    series, bands = _split_ratio_handles(handles)
    return ax.legend(
        handles=_row_major_ratio_handles(series, bands),
        loc="upper left",
        ncol=max(len(series), 1),
        **_ratio_legend_style(),
    )


def census_footnote(bands, style=None):
    role = bands_role(bands) or "this role"
    n = (bands or {}).get("n") or 0
    if style == "peers":
        peers = peers_word(bands)
        if n:
            return f"{n:,} {peers} · baseline 15 Aug 2026"
        return f"{peers} · baseline 15 Aug 2026"
    if n:
        return f"{role} write/read bands · frozen census, n={n}"
    return f"{role} write/read bands · frozen census"


def apply_census_footnote(fig, bands, y=0.012, under=None, offset_pt=5,
                         style=None):
    text = census_footnote(bands, style=style)
    if not text:
        return None
    if under is not None:
        return _text_just_under(
            fig, under, text, fontsize=7.5, color=GRAY, offset_pt=offset_pt,
        )
    return fig.text(0.01, y, text, fontsize=7.5, color=GRAY, va="bottom")


def band_legend_labels(bands, style=None):
    """Typical / Uncommon / Investigate copy. Same fields per style.

    Frozen numbers come from data/role_ratio_bands.json:
      typical = this role's p10–p90
      uncommon = the shoulders (p2–p10 and p90–p98)
      investigate = outside p2–p98
    Default style is judgment + range + percentile (range_pct).
    """
    style = style or DEFAULT_BAND_COPY
    bands = bands or {
        "role": "all relays",
        "typical_lo": RATIO_LO, "typical_hi": RATIO_HI,
        "invest_lo": RATIO_INVESTIGATE_LO, "invest_hi": RATIO_INVESTIGATE_HI,
        "n": 0,
    }
    role = bands.get("role") or "this role"
    n = bands.get("n") or 0
    tlo, thi = bands["typical_lo"], bands["typical_hi"]
    ilo, ihi = bands["invest_lo"], bands["invest_hi"]
    n_bit = f", n={n}" if n else ""
    rng_t = f"{tlo:.2f}–{thi:.2f}"
    rng_u_slash = f"{ilo:.2f}–{tlo:.2f} / {thi:.2f}–{ihi:.2f}"
    rng_u_or = f"{ilo:.2f}–{tlo:.2f} or {thi:.2f}–{ihi:.2f}"
    rng_i = f"<{ilo:.2f} or >{ihi:.2f}"
    if style == "full":
        return {
            "header": None,
            "typical": f"Typical  {rng_t}  ·  {role} p10–p90{n_bit}",
            "uncommon": (
                f"Uncommon  {rng_u_slash}  ·  {role} p2–p10 / p90–p98{n_bit}"
            ),
            "investigate": (
                f"Investigate  {rng_i}  ·  {role} beyond p98{n_bit}"
            ),
        }
    if style == "range_pct":
        return {
            "header": None,
            "typical": f"Typical  {rng_t}  ·  p10–p90",
            "uncommon": f"Uncommon  {rng_u_or}  ·  p2–p10 / p90–p98",
            "investigate": f"Investigate  {rng_i}  ·  <p2 or >p98",
        }
    if style == "range_only":
        return {
            "header": None,
            "typical": f"Typical  {rng_t}",
            "uncommon": f"Uncommon  {rng_u_or}",
            "investigate": f"Investigate  {rng_i}",
        }
    if style == "header":
        header = f"{role}  ·  n={n}" if n else role
        return {
            "header": header,
            "typical": f"Typical  {rng_t}  ·  p10–p90",
            "uncommon": f"Uncommon  {rng_u_or}  ·  p2–p10 / p90–p98",
            "investigate": f"Investigate  {rng_i}  ·  <p2 or >p98",
        }
    return {
        "header": None,
        "typical": f"Typical  {rng_t}  ·  {role} p10–p90{n_bit}",
        "uncommon": f"Uncommon  {rng_u_slash}",
        "investigate": f"Investigate  {rng_i}  ·  {role} beyond p98",
    }


def ratio_legend_handles(overlays=None, bands=None, band_copy=None):
    bands = bands or {
        "role": "all relays",
        "typical_lo": RATIO_LO, "typical_hi": RATIO_HI,
        "invest_lo": RATIO_INVESTIGATE_LO, "invest_hi": RATIO_INVESTIGATE_HI,
        "n": 0,
    }
    overlays = overlays or {}
    op_n = overlays.get("family_n") or 0
    copy = band_legend_labels(bands, band_copy or DEFAULT_BAND_COPY)
    handles = [
        Line2D([0], [0], color=NAVY, linewidth=1.6, label="This relay"),
    ]
    if overlays.get("operator"):
        handles.append(Line2D(
            [0], [0], color=GRAY, linestyle=":", linewidth=1.6,
            label=overlays.get("operator_label")
            or f"Operator Family (median, n={op_n})",
        ))
    if overlays.get("role"):
        handles.append(Line2D(
            [0], [0], color=SKY, linestyle="--", linewidth=1.4,
            label=overlays.get("role_label") or "Peers (network median)",
        ))
    if copy.get("header"):
        handles.append(Line2D(
            [], [], linestyle="None", marker="None", color="none",
            label=copy["header"],
        ))
    handles.extend([
        Patch(facecolor=GREEN, alpha=0.22, edgecolor=GREEN,
              label=copy["typical"]),
        Patch(facecolor=AMBER, alpha=0.16, edgecolor=AMBER,
              label=copy["uncommon"]),
        Patch(facecolor=BAD, alpha=0.16, edgecolor=BAD,
              label=copy["investigate"]),
    ])
    return handles


def _plot_ratio_strip(axr, ts, read_m, write_m, events, overlays=None,
                      legend_above=True, bands=None, show_legend=True,
                      period_key=None, band_copy=None, title=None,
                      title_loc="center", title_fontsize=None,
                      legend_loc="below", chrome=None, title_pad=None):
    overlays = overlays or {}
    bands = bands or overlays.get("bands") or {
        "role": "all relays",
        "typical_lo": RATIO_LO, "typical_hi": RATIO_HI,
        "invest_lo": RATIO_INVESTIGATE_LO, "invest_hi": RATIO_INVESTIGATE_HI,
    }
    tlo, thi = bands["typical_lo"], bands["typical_hi"]
    ilo, ihi = bands["invest_lo"], bands["invest_hi"]
    ratio = np.array([w / r if r else np.nan for w, r in zip(write_m, read_m)])
    ylo, yhi = 0.50, 1.70
    shelf = 0.52 if legend_loc == "shelf" else 0.0
    axr.axhspan(0.45, ilo, color=BAD, alpha=0.10, zorder=0)
    axr.axhspan(ilo, tlo, color=AMBER, alpha=0.10, zorder=0)
    axr.axhspan(tlo, thi, color=GREEN, alpha=0.16, zorder=0)
    axr.axhspan(thi, ihi, color=AMBER, alpha=0.10, zorder=0)
    axr.axhspan(ihi, yhi if shelf else 1.85, color=BAD, alpha=0.10, zorder=0)
    wt = chrome_weights(chrome)
    axr.axhline(1.0, color=GREEN, linestyle="--", linewidth=1.0, zorder=1)
    role = overlay_values(ts, overlays.get("role"))
    if role is not None:
        axr.plot(ts, role, color=SKY, linestyle="--", linewidth=wt["peers"],
                 zorder=2)
    op = overlay_values(ts, overlays.get("operator"))
    if op is not None:
        axr.plot(ts, op, color=GRAY, linestyle=":", linewidth=wt["family"],
                 zorder=2)
    # Clip to ylim. A Guard write spike (jeangrae 22–23 Jul, ratio 4.45 / 3.15)
    # is investigate and used to vanish — the navy line was masked and the
    # red line sat above 1.70.
    y_plot = np.clip(ratio, ylo, yhi)
    investigate = (ratio < ilo) | (ratio > ihi)
    axr.plot(ts, y_plot, color=NAVY, linewidth=wt["relay"], zorder=3)
    if investigate.any():
        axr.plot(ts, np.ma.masked_where(~investigate, y_plot),
                 color=BAD, linewidth=wt["investigate"], zorder=4)
    off_hi = np.isfinite(ratio) & (ratio > yhi)
    off_lo = np.isfinite(ratio) & (ratio < ylo)
    ts_arr = np.array(ts)
    if off_hi.any():
        axr.scatter(ts_arr[off_hi], np.full(int(off_hi.sum()), yhi),
                    marker="^", color=BAD, s=32, zorder=5, clip_on=False)
    if off_lo.any():
        axr.scatter(ts_arr[off_lo], np.full(int(off_lo.sum()), ylo),
                    marker="v", color=BAD, s=32, zorder=5, clip_on=False)
    draw_event_lines(axr, events, lw=wt["restart"])
    apply_chrome_axes(axr, chrome)
    pad_xlim(axr, ts)
    axr.set_ylabel("Write / read")
    axr.set_ylim(ylo, yhi + shelf)
    apply_ratio_yticks(axr, bands, ylo, yhi)
    if period_key:
        period_date_axis(axr, period_key)
    else:
        date_axis(axr)
    if show_legend:
        handles = ratio_legend_handles(overlays, bands, band_copy=band_copy)
        if legend_loc == "right":
            place_ratio_legend_right(axr, handles)
        elif legend_loc == "shelf":
            place_ratio_legend_shelf(axr, handles)
        else:
            place_ratio_legend_below(axr, handles)
    apply_ratio_title(axr, title, loc=title_loc, fontsize=title_fontsize,
                     pad=title_pad)
    return float(np.nanmean(ratio))


def apply_ratio_yticks(axr, bands, ylo=0.50, yhi=1.70):
    """Percentile labels live on the left axis with 0.5 / 1.0 / 1.5."""
    tlo, thi = bands["typical_lo"], bands["typical_hi"]
    ihi = bands["invest_hi"]
    typical_mid = (tlo + thi) / 2.0
    ticks = [ylo, 1.0, 1.5]
    labels = [f"{ylo:.1f}", "1.0", "1.5"]
    colors = [GRAY, GRAY, GRAY]
    if abs(typical_mid - 1.0) < 0.10:
        labels[1] = "1.0   p10–p90"
        colors[1] = GREEN
    else:
        ticks.insert(2 if typical_mid > 1.0 else 1, typical_mid)
        labels.insert(2 if typical_mid > 1.0 else 1, "p10–p90")
        colors.insert(2 if typical_mid > 1.0 else 1, GREEN)
    p98_y = min(yhi - 0.06, max(ihi + 0.05, (ihi + yhi) / 2.0))
    if 1.5 >= ihi or abs(p98_y - 1.5) <= 0.12:
        labels[ticks.index(1.5)] = "1.5   >p98"
        colors[ticks.index(1.5)] = BAD
    elif p98_y > 1.5:
        ticks.append(p98_y)
        labels.append(">p98")
        colors.append(BAD)
    axr.set_yticks(ticks)
    axr.set_yticklabels(labels)
    for tick, color in zip(axr.get_yticklabels(), colors):
        tick.set_color(color)
        if color != GRAY:
            tick.set_fontweight("bold")
            tick.set_fontsize(7.5)


def events_in_span(events, ts):
    if not ts:
        return []
    lo, hi = ts[0], ts[-1]
    out = []
    for ev in events or []:
        if ev.get("kind") == "overload":
            continue
        whens = [w for w in event_whens(ev) if lo <= w <= hi]
        if not whens:
            continue
        clipped = dict(ev)
        clipped["whens"] = whens
        clipped["when"] = whens[0]
        if ev.get("kind") == "restart":
            clipped["legend"] = restart_legend_label(whens)
        out.append(clipped)
    return out


def _draw_throughput_series(ax, ts, read_m, write_m, advertised_mbit, events,
                            fill=False, period_key=None, legend_rows=1,
                            compact=False, chrome=None, tight_ylim=False):
    ev = events_in_span(events, ts)
    wt = chrome_weights(chrome)
    lw_w = 1.0 if compact else wt["write"]
    lw_r = 1.0 if compact else wt["read"]
    if fill:
        ax.fill_between(ts, write_m, color=WRITE, alpha=0.22)
        ax.fill_between(ts, read_m, color=BLUE, alpha=0.22)
        ax.plot(ts, write_m, color=WRITE, linewidth=1.2)
        ax.plot(ts, read_m, color=BLUE, linewidth=1.2)
    else:
        ax.plot(ts, write_m, color=WRITE, linewidth=lw_w)
        ax.plot(ts, read_m, color=BLUE, linewidth=lw_r)
    if advertised_mbit:
        ax.axhline(advertised_mbit, color=ORANGE, linestyle="--",
                   linewidth=1.0 if compact else wt["advertised"])
    draw_event_lines(ax, ev, lw=1.0 if compact else wt["restart"])
    apply_chrome_axes(ax, chrome)
    pad_xlim(ax, ts)
    if compact:
        data_max = max(list(write_m) + list(read_m) + [0.0])
        ceiling = max(advertised_mbit or 0.0, data_max) or 1.0
        ax.set_ylim(0, ceiling * 1.12)
        ax.tick_params(labelsize=7)
    else:
        throughput_ylim(ax, read_m, write_m, advertised_mbit,
                        legend_rows=legend_rows, tight=tight_ylim)
        ax.set_ylabel("Throughput (Mbit/s)")
    if period_key:
        period_date_axis(ax, period_key)
    else:
        date_axis(ax)


def bandwidth_a_dual_line(ts, read_m, write_m, advertised_mbit, events, published,
                          overlays, overload_status, out_paths,
                          nickname="F3Netze",
                          operator=None,
                          identity_placement="above",
                          title=None,
                          overload_mode="title",
                          page_ready=False,
                          story=None,
                          bands=None,
                          period_key="1_month",
                          band_copy=None,
                          chrome=None,
                          legend_attach=None,
                          subtitle_style=None):
    bands = bands or (overlays or {}).get("bands")
    wrap_last = overload_mode == "legend" and bool(overload_status)
    if legend_attach is None:
        legend_attach = "above" if chrome else "split"
    outcome = summarize_bandwidth_outcome(
        ts, write_m, read_m, advertised_mbit, events, overlays, bands,
        overload_status,
    )
    if subtitle_style in OUTCOME_STYLES:
        thru_sub = format_outcome_subtitle(outcome, "throughput", subtitle_style)
        ratio_sub = format_outcome_subtitle(outcome, "ratio", subtitle_style)
        subtitle_on = bool(thru_sub or ratio_sub)
    elif subtitle_style == "none":
        thru_sub = ratio_sub = ""
        subtitle_on = False
    elif subtitle_style:
        thru_sub = throughput_subtitle_text(period_key, subtitle_style)
        ratio_sub = ratio_subtitle_text(bands, subtitle_style)
        subtitle_on = True
    else:
        thru_sub = ratio_sub = ""
        subtitle_on = bool(chrome and chrome.get("subtitle"))
        if subtitle_on:
            thru_sub = throughput_subtitle_text(period_key, subtitle_style)
            ratio_sub = ratio_subtitle_text(bands, subtitle_style)
    if legend_attach == "below":
        hspace = 0.62 if wrap_last else 0.48
        fig_h = 8.2 if wrap_last else 7.9
        if not subtitle_on:
            hspace -= 0.06
            fig_h -= 0.25
        top = 0.86 if subtitle_on else 0.91
        bottom = 0.20 if page_ready else 0.28
        height_ratios = [3.2, 1.35]
    elif chrome:
        hspace = 0.34 if subtitle_on else (0.24 if page_ready else 0.28)
        fig_h = 7.6 if (legend_attach == "above" and subtitle_on) else (
            7.4 if subtitle_on else (7.1 if page_ready else 8.3)
        )
        top = 0.86 if subtitle_on else 0.91
        bottom = 0.16 if page_ready else 0.26
        height_ratios = [3.2, 1.75] if legend_attach == "above" else [3.2, 1.35]
    else:
        hspace = 0.22 if page_ready else 0.26
        fig_h = 7.0 if page_ready else 8.2
        top = 0.91
        bottom = 0.16 if page_ready else 0.26
        height_ratios = [3.2, 1.35]
    ident = chart_identity(nickname, operator)
    identity_on = bool(ident) and identity_placement == "above"
    if identity_on:
        fig_h += IDENTITY_EXTRA_FIG_H
        top = max(0.70, top - IDENTITY_TOP_SHIFT)
    fig, (ax, axr) = plt.subplots(
        2, 1, figsize=(10.8, fig_h), sharex=True,
        gridspec_kw={"height_ratios": height_ratios, "hspace": hspace},
    )
    fig.subplots_adjust(top=top, bottom=bottom)
    plt.setp(ax.get_xticklabels(), visible=False)
    _draw_throughput_series(
        ax, ts, read_m, write_m, advertised_mbit, events,
        period_key=period_key, legend_rows=2 if wrap_last else 1,
        chrome=chrome, tight_ylim=(legend_attach == "below"),
    )
    if title is None:
        title = "Throughput · last 30 days"
    if identity_placement == "infront" and ident and title and ident not in title:
        title = f"{ident}  ·  {title}"
    bw_title = with_role(title, bands)
    title_loc = chrome_title_loc(chrome, overload_status, overload_mode)
    title_pad = SUBTITLE_TITLE_PAD if subtitle_on else THROUGHPUT_TITLE_PAD
    if identity_on:
        title_pad += IDENTITY_TITLE_PAD_BOOST
    used_pad = title_pad
    apply_throughput_title(
        ax, bw_title, overload_status, overload_mode,
        loc=title_loc, pad=title_pad,
    )
    if identity_on:
        apply_chart_identity(ax, ident, loc=title_loc, title_pad=used_pad)
    if thru_sub:
        apply_method_subtitle(ax, thru_sub)
    if chrome and chrome.get("callout"):
        auto_spike_callout(ax, ts, write_m, read_m, bands)
    bw_handles = throughput_legend_handles(
        advertised_mbit, events_in_span(events, ts), overload_status,
        overload_in_legend=(overload_mode == "legend"),
    )
    if legend_attach == "below":
        place_legend_below_axes(ax, bw_handles, wrap_last=wrap_last)
    else:
        place_legend_above_axes(ax, bw_handles, wrap_last=wrap_last)

    mean_ratio = _plot_ratio_strip(
        axr, ts, read_m, write_m, events, overlays, bands=bands,
        period_key=period_key, band_copy=band_copy,
        title=sibling_ratio_title(bw_title, bands),
        title_loc=title_loc,
        chrome=chrome, title_pad=title_pad,
        legend_loc="shelf" if legend_attach == "above" else "below",
    )
    if ratio_sub:
        apply_method_subtitle(axr, ratio_sub)
    ratio_legend = axr.get_legend()
    if not page_ready:
        used = 100.0 * np.mean(write_m) / advertised_mbit if advertised_mbit else 0
        fam_n = (overlays or {}).get("family_n") or 0
        fam_out = (overlays or {}).get("family_outliers") or 0
        thi = (bands or {}).get("typical_hi", RATIO_HI)
        off = sum(1 for w, r in zip(write_m, read_m) if r and (w / r) > 1.70)
        off_bit = (
            f" {off} day(s) sit above the 1.70 scale (red triangles) — "
            "the line was not missing."
            if off else ""
        )
        caption(
            fig, published,
            story or (
                f"Story: {nickname} mean write/read {mean_ratio:.2f}, "
                f"{ratio_zone_phrase(mean_ratio, bands)}. Bands are this "
                f"relay's flag set, frozen from a quiet census — not a live "
                f"percentile. Role overlay confirms whether the whole role "
                f"moved. {fam_out} of {fam_n} group relays sit above this "
                f"role's typical ({thi:.2f}). Delivered write "
                f"~{np.mean(write_m):.0f} Mbit/s ({used:.0f}% of advertised)."
                f"{off_bit}"
            ),
            footnote=census_footnote(bands),
            under=ratio_legend,
        )
    else:
        fn_style = (
            "peers" if subtitle_style in OUTCOME_STYLES else subtitle_style
        )
        if legend_attach == "above":
            apply_census_footnote(fig, bands, style=fn_style)
        else:
            apply_census_footnote(
                fig, bands, under=ratio_legend, style=fn_style,
            )
    save(fig, out_paths, trim=True)


def bandwidth_b_area_ratio(ts, read_m, write_m, advertised_mbit, events, published,
                           overlays, overload_status, out_paths):
    fig, (ax, axr) = plt.subplots(
        2, 1, figsize=(10.8, 8.0), sharex=True,
        gridspec_kw={"height_ratios": [3.1, 1.35], "hspace": 0.26},
    )
    fig.subplots_adjust(top=0.91, bottom=0.26)
    plt.setp(ax.get_xticklabels(), visible=False)
    _draw_throughput_series(ax, ts, read_m, write_m, advertised_mbit, events,
                            fill=True)
    b_bands = bands_for_flags(["Exit", "Guard"])
    apply_throughput_title(
        ax, with_role("Bandwidth B — overlapping area   ·   F3Netze", b_bands),
        overload_status, "title",
    )
    handles = [
        Patch(facecolor=WRITE, alpha=0.35, label="Write"),
        Patch(facecolor=BLUE, alpha=0.35, label="Read"),
    ]
    if advertised_mbit:
        handles.append(Line2D([0], [0], color=ORANGE, linestyle="--", linewidth=1.4,
                              label=f"Advertised  {advertised_mbit:.0f} Mbit/s"))
    handles.extend(event_legend_handles(events))
    place_legend_above_axes(ax, handles)
    strip_title = sibling_ratio_title(
        with_role("Throughput · last 30 days   ·   F3Netze", b_bands), b_bands,
    )
    _plot_ratio_strip(
        axr, ts, read_m, write_m, events, overlays, bands=b_bands,
        title=strip_title,
        title_loc=throughput_title_loc(overload_status, "title"),
    )
    caption(
        fig, published,
        "Same restart marker, title-line overload cue, Exit+Guard frozen "
        "bands (p10–p90 / beyond p98), and role / operator overlays as A. "
        "Area fill is the alternate encoding; A is the preferred default.",
        footnote=census_footnote(b_bands),
        under=axr.get_legend(),
    )
    save(fig, out_paths, trim=True)


def bandwidth_c_bars_advertised(ts, read_m, write_m, advertised_mbit, events,
                                published, overload_status, out_paths):
    fig, ax = plt.subplots(figsize=(10.8, 5.6))
    fig.subplots_adjust(top=0.88, bottom=0.16)
    x = np.arange(len(ts))
    w = 0.38
    ax.bar(x - w / 2, write_m, w, color=WRITE, label="Write")
    ax.bar(x + w / 2, read_m, w, color=BLUE, label="Read")
    if advertised_mbit:
        ax.axhline(
            advertised_mbit, color=ORANGE, linestyle="--", linewidth=1.4,
            label=f"Advertised  {advertised_mbit:.0f} Mbit/s",
        )
    draw_event_lines(ax, events, x_values=ts)
    pad_xlim(ax, ts, x_values=ts)
    ax.set_ylabel("Throughput (Mbit/s)")
    apply_throughput_title(
        ax, "Bandwidth C — daily bars vs advertised   ·   F3Netze",
        overload_status, "title",
    )
    tick = list(range(0, len(ts), 4))
    ax.set_xticks(tick, [ts[i].strftime("%b %d") for i in tick])
    handles = [
        Patch(facecolor=WRITE, label="Write"),
        Patch(facecolor=BLUE, label="Read"),
    ]
    if advertised_mbit:
        handles.append(Line2D([0], [0], color=ORANGE, linestyle="--", linewidth=1.4,
                              label=f"Advertised  {advertised_mbit:.0f} Mbit/s"))
    handles.extend(event_legend_handles(events))
    place_legend_above_axes(ax, handles)
    used = 100.0 * np.mean(write_m) / advertised_mbit if advertised_mbit else 0
    caption(
        fig, published,
        f"Story: this exit advertises {advertised_mbit:.0f} Mbit/s and delivers "
        f"~{np.mean(write_m):.0f} Mbit/s write ({used:.0f}% of advertised). "
        "Restart is a point. Overload is a title cue, not a time range — "
        "Onionoo has no incident history.",
    )
    save(fig, out_paths)


def load_bandwidth_periods(bw_relay):
    """Align write/read for each Onionoo period Onionoo actually published."""
    out = {}
    wh = bw_relay.get("write_history") or {}
    rh = bw_relay.get("read_history") or {}
    for key in PERIOD_ORDER:
        w_ts, w_vals = history_series(wh.get(key))
        r_ts, r_vals = history_series(rh.get(key))
        if not w_ts or not r_ts:
            continue
        wmap = dict(zip(w_ts, w_vals))
        rmap = dict(zip(r_ts, r_vals))
        keys = sorted(set(wmap) & set(rmap))
        if len(keys) < 2:
            continue
        out[key] = {
            "ts": keys,
            "write_m": bytes_to_mbit([wmap[t] for t in keys]),
            "read_m": bytes_to_mbit([rmap[t] for t in keys]),
        }
    return out


def _period_overlays(overlays, key):
    """Role / family daily overlays only line up on 1-month buckets."""
    if key == "1_month":
        return overlays or {}
    slim = dict(overlays or {})
    slim["role"] = {}
    slim["operator"] = {}
    return slim


def bandwidth_periods_pills(periods, selected_key, advertised_mbit, events,
                            overlays, overload_status, published, nickname,
                            out_paths, page_ready=True):
    """Period-pill toggle. Missing Onionoo graphs are omitted, not drawn as 0."""
    meta = BW_PERIOD_META[selected_key]
    block = periods[selected_key]
    ts, write_m, read_m = block["ts"], block["write_m"], block["read_m"]
    wrap_last = bool(overload_status)
    fig = plt.figure(figsize=(10.8, 8.4 if page_ready else 9.0))
    available = [BW_PERIOD_META[k]["short"] for k in PERIOD_ORDER if k in periods]
    draw_period_pills(fig, available, meta["short"])
    ax = fig.add_axes([0.08, 0.50, 0.90, 0.32])
    axr = fig.add_axes([0.08, 0.22 if page_ready else 0.26, 0.90, 0.20], sharex=ax)
    _draw_throughput_series(
        ax, ts, read_m, write_m, advertised_mbit, events,
        period_key=selected_key, legend_rows=2 if wrap_last else 1,
    )
    bands = (overlays or {}).get("bands")
    bw_title = with_role(
        f"Throughput · {meta['title']}  ·  {meta['bucket']} buckets",
        bands,
    )
    apply_throughput_title(ax, bw_title, overload_status, "legend")
    place_legend_above_axes(
        ax,
        throughput_legend_handles(
            advertised_mbit, events_in_span(events, ts), overload_status,
            overload_in_legend=True,
        ),
        wrap_last=wrap_last,
    )
    _plot_ratio_strip(
        axr, ts, read_m, write_m, events, _period_overlays(overlays, selected_key),
        bands=bands, period_key=selected_key,
        title=sibling_ratio_title(bw_title, bands),
        title_loc=throughput_title_loc(overload_status, "legend"),
    )
    extra = _span_note(ts, selected_key)
    if extra:
        ax.text(0.99, 0.04, extra, transform=ax.transAxes, ha="right",
                va="bottom", fontsize=8, color=GRAY)
    if not page_ready:
        missing = [BW_PERIOD_META[k]["short"] for k in PERIOD_ORDER
                   if k not in periods]
        omit = (", omitted " + ", ".join(missing)) if missing else ""
        caption(
            fig, published,
            f"Period pills on {nickname}. Onionoo published "
            f"{', '.join(available)}{omit}. A static site cannot fetch on "
            f"click — each pill is a pre-rendered SVG.",
            footnote=census_footnote((overlays or {}).get("bands")),
            under=axr.get_legend(),
        )
    else:
        apply_census_footnote(
            fig, (overlays or {}).get("bands"), under=axr.get_legend(),
        )
    save(fig, out_paths)


def bandwidth_periods_equal(periods, advertised_mbit, events, overload_status,
                            published, nickname, out_paths, page_ready=True):
    """Equal 2×2 of every published graph. Empty cell = Onionoo omitted it."""
    fig, axes = plt.subplots(2, 2, figsize=(10.8, 6.8))
    fig.subplots_adjust(bottom=0.08 if page_ready else 0.14, top=0.86,
                        hspace=0.42, wspace=0.22)
    fig.suptitle(f"Throughput · all published graphs   ·   {nickname}",
                 fontsize=13, fontweight="bold")
    handles = throughput_legend_handles(
        advertised_mbit, events, overload_status, overload_in_legend=True,
    )
    if overload_status and len(handles) > 1:
        fig.legend(
            handles=handles[:-1], loc="upper left", bbox_to_anchor=(0.08, 0.98),
            ncol=len(handles) - 1, fontsize=8.0, frameon=False,
            columnspacing=1.0,
        )
        fig.legend(
            handles=handles[-1:], loc="upper left", bbox_to_anchor=(0.08, 0.945),
            ncol=1, fontsize=8.0, frameon=False,
        )
    else:
        fig.legend(
            handles=handles, loc="upper left", bbox_to_anchor=(0.08, 0.98),
            ncol=min(len(handles), 4), fontsize=8.0, frameon=False,
        )
    for i, key in enumerate(PERIOD_ORDER):
        ax = axes[i // 2][i % 2]
        meta = BW_PERIOD_META[key]
        if key not in periods:
            ax.set_axis_off()
            ax.text(
                0.5, 0.5,
                f"{meta['short']}  ·  not published\nOnionoo omitted this graph",
                ha="center", va="center", color=GRAY, fontsize=11,
                transform=ax.transAxes,
            )
            continue
        block = periods[key]
        _draw_throughput_series(
            ax, block["ts"], block["read_m"], block["write_m"],
            advertised_mbit, events, period_key=key, compact=True,
        )
        extra = _span_note(block["ts"], key)
        ax.set_title(
            f"{meta['short']}  ·  {meta['bucket']} buckets"
            + (f"\n{extra}" if extra else ""),
            fontsize=10,
        )
        ax.set_ylabel("Mbit/s", fontsize=8)
    if not page_ready:
        caption(
            fig, published,
            f"Equal panels on {nickname}. Same advertised snapshot on every "
            "panel (not a history). Empty cell = omitted graph, not 0 Mbit/s.",
        )
    save(fig, out_paths)


def bandwidth_periods_hero_sparks(periods, advertised_mbit, events, overlays,
                                  overload_status, published, nickname,
                                  out_paths, page_ready=True, hero_key=None):
    """Hero (throughput + ratio) and smaller sparks for the other graphs.

    Clicking a spark swaps it with the hero (static site: pre-render each
    hero_key and swap the images).
    """
    if hero_key is None or hero_key not in periods:
        hero_key = "1_month" if "1_month" in periods else next(iter(periods))
    others = [k for k in PERIOD_ORDER if k in periods and k != hero_key]
    wrap_last = bool(overload_status)
    fig = plt.figure(figsize=(10.8, 9.8 if others else 8.2))
    ax = fig.add_axes([0.08, 0.58 if others else 0.42, 0.90, 0.28 if others else 0.42])
    axr = fig.add_axes([0.08, 0.36 if others else 0.22, 0.90, 0.14], sharex=ax)
    block = periods[hero_key]
    meta = BW_PERIOD_META[hero_key]
    _draw_throughput_series(
        ax, block["ts"], block["read_m"], block["write_m"], advertised_mbit,
        events, period_key=hero_key, legend_rows=2 if wrap_last else 1,
    )
    bands = (overlays or {}).get("bands")
    bw_title = with_role(
        f"Throughput · {meta['title']}  ·  {meta['bucket']} buckets",
        bands,
    )
    apply_throughput_title(ax, bw_title, overload_status, "legend")
    place_legend_above_axes(
        ax,
        throughput_legend_handles(
            advertised_mbit, events_in_span(events, block["ts"]),
            overload_status, overload_in_legend=True,
        ),
        wrap_last=wrap_last,
    )
    _plot_ratio_strip(
        axr, block["ts"], block["read_m"], block["write_m"], events,
        _period_overlays(overlays, hero_key), bands=bands, show_legend=True,
        period_key=hero_key, title=sibling_ratio_title(bw_title, bands),
        title_loc=throughput_title_loc(overload_status, "legend"),
    )
    if others:
        n = len(others)
        width = 0.90 / n
        for i, key in enumerate(others):
            a = fig.add_axes([0.08 + i * width, 0.06, width - 0.03, 0.16])
            b = periods[key]
            _draw_throughput_series(
                a, b["ts"], b["read_m"], b["write_m"], advertised_mbit,
                events, period_key=key, compact=True,
            )
            m = BW_PERIOD_META[key]
            a.set_title(f"{m['short']}  ·  {m['bucket']}  ·  click to swap",
                        fontsize=9)
            a.set_ylabel("")
    if not page_ready:
        caption(
            fig, published,
            f"Hero is {BW_PERIOD_META[hero_key]['short']} on {nickname}. "
            "Click a spark to move it to the hero slot; the previous hero "
            "drops into the spark row. Omit a spark if Onionoo omitted the graph.",
            footnote=census_footnote((overlays or {}).get("bands")),
        )
    else:
        apply_census_footnote(fig, (overlays or {}).get("bands"), y=0.012)
    save(fig, out_paths)


def save_period_spark(block, advertised_mbit, events, key, out_paths):
    """Compact throughput tile used as a clickable spark."""
    fig, ax = plt.subplots(figsize=(3.9, 2.15))
    fig.subplots_adjust(left=0.16, right=0.97, top=0.80, bottom=0.22)
    _draw_throughput_series(
        ax, block["ts"], block["read_m"], block["write_m"],
        advertised_mbit, events, period_key=key, compact=True,
    )
    m = BW_PERIOD_META[key]
    ax.set_title(f"{m['short']}  ·  {m['bucket']}", fontsize=9)
    save(fig, out_paths)


def write_hero_sparks_swap_html(path, nickname, periods, hero_name, spark_name):
    """Click a spark: it becomes the hero, previous hero joins the spark row."""
    keys = [k for k in PERIOD_ORDER if k in periods]
    shorts = {k: BW_PERIOD_META[k]["short"] for k in keys}
    heroes = {k: hero_name(k) for k in keys}
    sparks = {k: spark_name(k) for k in keys}
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{nickname} — hero + sparks swap</title>
  <style>
    .hs-wrap {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; }}
    .hs-note {{ font-size:12px; color:#555; margin:0 0 8px; }}
    .hs-hero img {{ width:100%; height:auto; display:block; }}
    .hs-sparks {{ display:flex; gap:10px; margin-top:8px; }}
    .hs-sparks button {{
      flex:1; padding:4px; border:1px solid #dee2e6; background:#fff;
      cursor:pointer; border-radius:6px;
    }}
    .hs-sparks button:hover {{ border-color:#337ab7; }}
    .hs-sparks button img {{ width:100%; height:auto; display:block; }}
    .hs-sparks button span {{
      display:block; font-size:11px; color:#1b3a4b; margin-top:4px;
    }}
  </style>
</head>
<body>
<div class="hs-wrap">
  <p class="hs-note">Click a spark to swap it with the hero. The previous
  hero moves into the spark row. Unpublished Onionoo graphs are omitted.</p>
  <div class="hs-hero"><img id="hs-hero-img" alt="Hero throughput"></div>
  <div class="hs-sparks" id="hs-sparks"></div>
</div>
<script>
const KEYS = {json.dumps(keys)};
const SHORT = {json.dumps(shorts)};
const HERO = {json.dumps(heroes)};
const SPARK = {json.dumps(sparks)};
let hero = KEYS.includes("1_month") ? "1_month" : KEYS[0];
function render() {{
  document.getElementById("hs-hero-img").src = HERO[hero];
  const row = document.getElementById("hs-sparks");
  row.innerHTML = KEYS.filter(k => k !== hero).map(k =>
    '<button type="button" data-key="'+k+'">' +
    '<img src="'+SPARK[k]+'" alt="'+SHORT[k]+' spark">' +
    '<span>'+SHORT[k]+' · click to swap</span></button>'
  ).join("");
}}
document.getElementById("hs-sparks").addEventListener("click", (e) => {{
  const btn = e.target.closest("button");
  if (!btn) return;
  hero = btn.getAttribute("data-key");
  render();
}});
render();
</script>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path


# ---------------------------------------------------------------------------
# Extra relay-page chart — flag flapping (th4r)
# ---------------------------------------------------------------------------

def series_interval(ts):
    if len(ts) < 2:
        return timedelta(hours=4)
    return ts[1] - ts[0]


def episodes_from_pct(ts, pct, thresh=99.0):
    """Contiguous runs below thresh, with interval-midpoint windows."""
    half = series_interval(ts) / 2
    out = []
    for i0, i1 in dip_spans(ts, pct, thresh):
        start = ts[i0] - half
        end = ts[i1] + half
        vals = pct[i0:i1 + 1]
        out.append({
            "i0": i0,
            "i1": i1,
            "start": start,
            "end": end,
            "hours": (end - start).total_seconds() / 3600.0,
            "min": min(vals),
            "n": i1 - i0 + 1,
        })
    return out


def fmt_dur(hours):
    if hours < 24:
        return f"{hours:.0f}h"
    days = hours / 24.0
    text = f"{days:.1f}d"
    return text.replace(".0d", "d")


def flags_held_vs_moved(flag_series):
    run = dict(zip(*flag_series["Running"]))
    held, moved = [], []
    for name, (ts, pct) in flag_series.items():
        if name == "Running":
            continue
        same = all(abs(p - run.get(t, p)) < 1.0 for t, p in zip(ts, pct))
        (held if same else moved).append(name)
    return held, moved


def hsdir_story(flag_series):
    """Major HSDir losses, a flapping stretch, and Running-gap triggers."""
    hs_ts, hs_pct = flag_series["HSDir"]
    run_ts, run_pct = flag_series["Running"]
    raw = episodes_from_pct(hs_ts, hs_pct, 99.0)
    gaps = episodes_from_pct(run_ts, run_pct, 99.0)
    major, short = [], []
    for e in raw:
        (major if e["hours"] >= 36 else short).append(e)
    flap = None
    if short:
        flap = {
            "start": min(e["start"] for e in short),
            "end": max(e["end"] for e in short),
            "hours": None,
            "kind": "flap",
        }
        flap["hours"] = (flap["end"] - flap["start"]).total_seconds() / 3600.0
    still = bool(hs_pct) and hs_pct[-1] < 50
    held, moved = flags_held_vs_moved(flag_series)
    return {
        "hs_ts": hs_ts,
        "hs_pct": hs_pct,
        "run_ts": run_ts,
        "run_pct": run_pct,
        "raw": raw,
        "major": major,
        "flap": flap,
        "gaps": gaps,
        "still": still,
        "held": held,
        "moved": moved,
    }


def _draw_running_gap_marks(ax, gaps, y=1.22, label=True):
    for g in gaps:
        x = g["start"] + (g["end"] - g["start"]) / 2
        ax.axvline(x, color=BAD, alpha=0.22, linewidth=1.1, zorder=2)
        ax.plot(x, y, marker="v", color=BAD, markersize=8, zorder=5)
        if label:
            ax.text(x, y + 0.14, g["start"].strftime("%-d %b"),
                    ha="center", va="bottom", fontsize=7, color=BAD)


def flags_a_swimlane(flag_series, published, out_paths):
    names = list(flag_series.keys())
    # align on union of timestamps via first series
    ts0 = flag_series[names[0]][0]
    mat = np.full((len(names), len(ts0)), np.nan)
    for i, name in enumerate(names):
        ts, pct = flag_series[name]
        by_t = {t: v for t, v in zip(ts, pct)}
        for j, t in enumerate(ts0):
            if t in by_t:
                mat[i, j] = by_t[t]

    fig, ax = plt.subplots(figsize=(11.2, 5.2))
    fig.subplots_adjust(bottom=0.20)
    mesh = ax.imshow(
        mat, aspect="auto", cmap=FLAG_CMAP, vmin=0, vmax=100,
        interpolation="nearest",
    )
    ax.set_yticks(range(len(names)), names)
    tick = list(range(0, len(ts0), 18))
    ax.set_xticks(tick, [ts0[i].strftime("%b %d") for i in tick])
    ax.set_title("Flags A — presence swimlane   ·   th4r (currently missing HSDir)")
    ax.grid(False)
    cbar = fig.colorbar(mesh, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("% of 4h window with flag")
    # outline the HSDir row
    if "HSDir" in names:
        i = names.index("HSDir")
        ax.add_patch(plt.Rectangle(
            (-0.5, i - 0.5), len(ts0), 1,
            fill=False, edgecolor=BAD, linewidth=1.4,
        ))
    caption(
        fig, published,
        "Question: which flags were present, when? Running / Guard / Stable stay "
        "green; HSDir drops for days after each gap. Weakness: the 4h Running "
        "gaps that cause the loss are hairline slivers, and three rows are copies.",
    )
    save(fig, out_paths)


def flags_b_overlay(flag_series, published, out_paths):
    colors = {
        "Running": BLUE,
        "Guard": GREEN,
        "Stable": ORANGE,
        "HSDir": BAD,
        "Exit": SKY,
    }
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    fig.subplots_adjust(bottom=0.20)
    for name, (ts, pct) in flag_series.items():
        ax.plot(ts, pct, color=colors.get(name, GRAY), linewidth=1.7, label=name)
    ax.set_ylim(-2, 108)
    ax.set_ylabel("Share of 4-hour window with flag (%)")
    ax.set_title("Flags B — overlay   ·   th4r")
    date_axis(ax)
    ax.legend(loc="lower left", ncol=4)
    caption(
        fig, published,
        "Question: how did each flag's presence % move? HSDir divergence is "
        "obvious, but Running / Guard / Stable sit on top of each other at 99% "
        "and hide the gaps that triggered the loss.",
    )
    save(fig, out_paths)


def flags_c_cause_effect(flag_series, published, extra, out_paths):
    s = hsdir_story(flag_series)
    ts, pct = s["hs_ts"], s["hs_pct"]
    present = np.array([p >= 50 for p in pct])
    fig, ax = plt.subplots(figsize=(11.2, 5.0))
    fig.subplots_adjust(bottom=0.22, top=0.82)
    ax.fill_between(ts, 0, 1, where=present, color=GREEN, step="mid",
                    linewidth=0, alpha=0.9, zorder=1)
    ax.fill_between(ts, 0, 1, where=~present, color=BAD, step="mid",
                    linewidth=0, alpha=0.9, zorder=1)
    _draw_running_gap_marks(ax, s["gaps"], y=1.18)
    for e in s["major"]:
        mid = e["start"] + (e["end"] - e["start"]) / 2
        label = fmt_dur(e["hours"])
        if s["still"] and e is s["major"][-1]:
            label += "\nstill missing"
        ax.text(mid, 0.50, label, ha="center", va="center", color="white",
                fontsize=8, fontweight="bold", zorder=4)
    if s["flap"]:
        mid = s["flap"]["start"] + (s["flap"]["end"] - s["flap"]["start"]) / 2
        ax.text(mid, 0.50, "flapping", ha="center", va="center", color="white",
                fontsize=7, zorder=4)
    ax.set_ylim(-0.08, 1.55)
    ax.set_yticks([0.5], ["HSDir"])
    ax.set_title("Flags C — cause → effect   ·   th4r")
    date_axis(ax)
    ax.legend(
        handles=[
            Patch(facecolor=GREEN, label="HSDir present"),
            Patch(facecolor=BAD, label="HSDir absent"),
            Line2D([0], [0], marker="v", color=BAD, linestyle="None",
                   markersize=8, label="Running gap (4h bucket)"),
        ],
        loc="upper left", fontsize=8, ncol=3,
    )
    held = " · ".join(s["held"]) if s["held"] else "none"
    caption(
        fig, published,
        f"Question: did a brief Running gap cost me a role flag, and for how "
        f"long? Triangles are Running gaps. Each multi-day red band starts at "
        f"one. Held all month (not plotted): {held}. "
        f"No process restart (last_restarted {extra['last_restarted']}).",
    )
    save(fig, out_paths)


def flags_d_episodes(flag_series, published, extra, out_paths):
    s = hsdir_story(flag_series)
    chrono = []
    for i, e in enumerate(s["major"]):
        is_open = s["still"] and i == len(s["major"]) - 1
        suffix = "+" if is_open else ""
        label = (
            f"{fmt_dur(e['hours'])}{suffix}  still missing"
            if is_open else f"{fmt_dur(e['hours'])} lost"
        )
        chrono.append({
            "label": label,
            "sub": f"after Running gap {e['start'].strftime('%-d %b %H:%M')}",
            "start": e["start"],
            "end": e["end"],
            "color": BAD,
        })
        if i == 0 and s["flap"]:
            chrono.append({
                "label": "Flapping",
                "sub": "weak recovery, not a new gap",
                "start": s["flap"]["start"],
                "end": s["flap"]["end"],
                "color": ORANGE,
            })
    rows = list(reversed(chrono))
    fig, ax = plt.subplots(figsize=(11.2, 5.4))
    fig.subplots_adjust(bottom=0.20, left=0.28)
    xmin = s["hs_ts"][0]
    xmax = s["hs_ts"][-1] + series_interval(s["hs_ts"])
    for i, row in enumerate(rows):
        ax.barh(
            i,
            mdates.date2num(row["end"]) - mdates.date2num(row["start"]),
            left=mdates.date2num(row["start"]),
            height=0.62,
            color=row["color"],
            alpha=0.88,
        )
    for g in s["gaps"]:
        x = g["start"] + (g["end"] - g["start"]) / 2
        ax.axvline(x, color=NAVY, linestyle=":", linewidth=1.2, alpha=0.7, zorder=0)
    ax.set_yticks(
        range(len(rows)),
        [f"{r['label']}\n{r['sub']}" for r in rows],
    )
    ax.set_xlim(mdates.date2num(xmin), mdates.date2num(xmax))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax.invert_yaxis()
    ax.set_title("Flags D — loss episodes   ·   th4r")
    ax.legend(
        handles=[
            Patch(facecolor=BAD, label="HSDir absent"),
            Patch(facecolor=ORANGE, label="Flapping / weak recovery"),
            Line2D([0], [0], color=NAVY, linestyle=":", linewidth=1.2,
                   label="Running gap"),
        ],
        loc="lower right", fontsize=8, ncol=3,
    )
    n_major = len(s["major"])
    caption(
        fig, published,
        f"Question: how many times did I lose HSDir this month, and how long "
        f"each time? {n_major} multi-day losses"
        f"{' · last one still open' if s['still'] else ''}. "
        f"Dotted lines are Running gaps. "
        f"No process restart (last_restarted {extra['last_restarted']}).",
    )
    save(fig, out_paths)


def flags_e_diverged_only(flag_series, published, extra, out_paths):
    s = hsdir_story(flag_series)
    fig, axes = plt.subplots(
        2, 1, figsize=(11.2, 4.8), sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.12},
    )
    fig.subplots_adjust(bottom=0.22, top=0.84)

    def strip(ax, ts, pct, name, mark_gaps=False):
        present = np.array([p >= 50 for p in pct])
        ax.fill_between(ts, 0, 1, where=present, color=GREEN, step="mid",
                        linewidth=0, alpha=0.9)
        ax.fill_between(ts, 0, 1, where=~present, color=BAD, step="mid",
                        linewidth=0, alpha=0.9)
        if mark_gaps:
            for g in s["gaps"]:
                ax.axvspan(g["start"], g["end"], color=BAD, alpha=0.55, zorder=3)
        ax.set_ylim(-0.15, 1.15)
        ax.set_yticks([0.5], [name])
        ax.set_ylabel("")

    strip(axes[0], s["run_ts"], s["run_pct"], "Running", mark_gaps=True)
    strip(axes[1], s["hs_ts"], s["hs_pct"], "HSDir")
    date_axis(axes[1])
    axes[0].set_title("Flags E — only flags that moved   ·   th4r")
    axes[0].legend(
        handles=[
            Patch(facecolor=GREEN, label="Present"),
            Patch(facecolor=BAD, label="Absent / gap"),
        ],
        loc="upper left", fontsize=8, ncol=2,
    )
    held = " · ".join(s["held"]) if s["held"] else "none"
    caption(
        fig, published,
        f"Question: which of my flags actually moved, and did they move "
        f"together? Running gaps are widened so a 4h miss is visible. HSDir "
        f"does not track Running — it stays down for days. Held (identical "
        f"to Running, omitted): {held}.",
    )
    save(fig, out_paths)


def flags_f_status_story(flag_series, published, extra, out_paths):
    s = hsdir_story(flag_series)
    fig = plt.figure(figsize=(11.2, 5.4))
    fig.subplots_adjust(bottom=0.16, top=0.93, left=0.07, right=0.97)
    gs = fig.add_gridspec(2, 1, height_ratios=[2.1, 1.0], hspace=0.28)
    ax_t = fig.add_subplot(gs[0])
    ax_s = fig.add_subplot(gs[1])
    ax_t.axis("off")
    ax_t.set_xlim(0, 1)
    ax_t.set_ylim(0, 1)

    last = s["major"][-1] if s["major"] else None
    if s["still"] and last:
        headline = "HSDir is missing"
        since = (
            f"since {last['start'].strftime('%-d %b %H:%M')} UTC  ·  "
            f"{fmt_dur(last['hours'])} and counting"
        )
        head_color = BAD
    elif last:
        headline = "HSDir is present now"
        since = (
            f"last loss ended {last['end'].strftime('%-d %b %H:%M')} UTC  ·  "
            f"lasted {fmt_dur(last['hours'])}"
        )
        head_color = GREEN
    else:
        headline = "HSDir held all month"
        since = "No absence in this window"
        head_color = GREEN

    ax_t.text(0.0, 0.92, "Flags F — status + month story   ·   th4r",
              fontsize=13, fontweight="bold", va="top")
    ax_t.text(0.0, 0.72, headline, fontsize=20, fontweight="bold",
              color=head_color, va="top")
    ax_t.text(0.0, 0.54, since, fontsize=12, color=NAVY, va="top")

    n_major = len(s["major"])
    longest = max((e["hours"] for e in s["major"]), default=0)
    lines = [
        f"This month: {n_major} multi-day losses"
        + (" · last one still open" if s["still"] else ""),
        f"Longest gap {fmt_dur(longest)}"
        + (" · plus a flapping stretch after a weak recovery (24–26 Jul)"
           if s["flap"] else ""),
        "Each multi-day loss starts at a Running gap — not a process restart.",
        f"last_restarted {extra['last_restarted']}  ·  "
        "HSDir needs WFU ≥ 98% (recent downtime weighted more); "
        "this is not a countdown.",
        "Held all month: " + (" · ".join(s["held"]) if s["held"] else "none"),
    ]
    ax_t.text(0.0, 0.38, "\n".join(lines), fontsize=9, color=GRAY, va="top",
              linespacing=1.45)

    ts, pct = s["hs_ts"], s["hs_pct"]
    present = np.array([p >= 50 for p in pct])
    ax_s.fill_between(ts, 0, 1, where=present, color=GREEN, step="mid",
                      linewidth=0, alpha=0.9)
    ax_s.fill_between(ts, 0, 1, where=~present, color=BAD, step="mid",
                      linewidth=0, alpha=0.9)
    _draw_running_gap_marks(ax_s, s["gaps"], y=1.18, label=False)
    ax_s.set_ylim(-0.1, 1.35)
    ax_s.set_yticks([0.5], ["HSDir"])
    date_axis(ax_s)
    caption(
        fig, published,
        "Question: do I have the flag right now, and what is the last-month "
        "story in one glance? The eligibility table already answers snapshot "
        "prereqs (WFU / TK / Fast / Stable). This answers since when, how "
        "often, and whether a Running gap was the trigger.",
        y=0.01,
    )
    save(fig, out_paths)


def history_map(block):
    """Return {timestamp: bytes_per_sec} skipping nulls."""
    ts, vals = history_series(block)
    return dict(zip(ts, vals))


def compute_group_daily_ratios(bw_by_fp, fingerprints, min_bps=50_000):
    """Daily median write/read and per-relay month-means for a fingerprint set."""
    from collections import defaultdict

    days = defaultdict(list)
    month_means = []
    used = 0
    for fp in fingerprints:
        doc = bw_by_fp.get(fp)
        if not doc:
            continue
        w = history_map((doc.get("write_history") or {}).get("1_month"))
        r = history_map((doc.get("read_history") or {}).get("1_month"))
        if not w or not r:
            continue
        wsum = rsum = 0.0
        any_pt = False
        for t, wv in w.items():
            rv = r.get(t)
            if not rv:
                continue
            if (wv + rv) / 2.0 < min_bps:
                continue
            days[t].append(wv / rv)
            wsum += wv
            rsum += rv
            any_pt = True
        if any_pt and rsum:
            month_means.append(wsum / rsum)
            used += 1
    daily = {t: float(np.median(vals)) for t, vals in days.items() if vals}
    return daily, month_means, used


def build_ratio_overlays(details_relays, bw_by_fp, role, contact_substr=None,
                         family_fps=None, operator_label=None):
    role_fps = [r["fingerprint"] for r in details_relays if role_of(r.get("flags")) == role]
    op_fps = []
    if family_fps:
        op_fps = list(family_fps)
    elif contact_substr:
        needle = contact_substr.lower()
        op_fps = [
            r["fingerprint"] for r in details_relays
            if needle in (r.get("contact") or "").lower()
        ]
    role_daily, _, role_n = compute_group_daily_ratios(bw_by_fp, role_fps)
    op_daily, op_means, op_n = compute_group_daily_ratios(bw_by_fp, op_fps)
    outliers = sum(1 for m in op_means if m > RATIO_HI)
    return {
        "role": role_daily,
        "role_label": "Peers (network median)",
        "operator": op_daily if op_n > 1 else {},
        "operator_label": operator_label or f"Operator Family (median, n={op_n})",
        "family_outliers": outliers,
        "family_n": op_n,
    }


def restart_events(relay, extra=None):
    """One legend entry, one vline per restart in range.

    Onionoo only publishes last_restarted. extra= is a mock / future
    archive of older restarts (CollecTor), newest first in the label.
    """
    whens = []
    if relay.get("last_restarted"):
        whens.append(parse_onionoo_ts(relay["last_restarted"]))
    for item in extra or []:
        if isinstance(item, str):
            item = parse_onionoo_ts(item)
        whens.append(item)
    # unique, newest first
    uniq = []
    seen = set()
    for w in sorted(whens, reverse=True):
        key = w.isoformat()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(w)
    if not uniq:
        return []
    return [{
        "kind": "restart",
        "when": uniq[0],
        "whens": uniq,
        "color": RESTART,
        "ls": "-.",
        "legend": restart_legend_label(uniq),
    }]


def load_bandwidth_for_fp(bw_doc, extra_paths, fp):
    if fp in bw_doc:
        return bw_doc[fp]
    for path in extra_paths:
        p = Path(path)
        if not p.exists():
            continue
        extra = by_fp(json.loads(p.read_text()))
        if fp in extra:
            return extra[fp]
    return None


def format_mb_s(byte_s):
    if not byte_s:
        return "N/A"
    if byte_s >= 1_000_000_000:
        return f"{byte_s / 1_000_000_000:.2f} GB/s"
    if byte_s >= 1_000_000:
        return f"{byte_s / 1_000_000:.2f} MB/s"
    return f"{byte_s / 1_000:.0f} KB/s"


def days_ago(ts_str, published):
    try:
        then = parse_onionoo_ts(ts_str)
        now = parse_onionoo_ts(published) if isinstance(published, str) else published
        days = max(0, int((now - then).total_seconds() // 86400))
    except (TypeError, ValueError):
        return ts_str
    if days == 0:
        return "today"
    if days == 1:
        return "1 day ago"
    if days < 60:
        return f"{days} days ago"
    months = days // 30
    return f"{months} months ago" if months != 1 else "1 month ago"


def relay_page_context(det, published, role_label):
    flags = [f for f in (det.get("flags") or []) if f != "StaleDesc"]
    cw_frac = det.get("consensus_weight_fraction") or 0
    guard_p = det.get("guard_probability") or 0
    mid_p = det.get("middle_probability") or 0
    exit_p = det.get("exit_probability") or 0
    contact = det.get("contact") or ""
    aroi = operator_from_contact(contact) or None
    return {
        "nickname": det.get("nickname") or "unknown",
        "fingerprint": det.get("fingerprint") or "",
        "flags": flags,
        "flag_str": ", ".join(flags),
        "country": (det.get("country") or "").upper(),
        "country_name": {
            "de": "Germany", "us": "United States", "nl": "Netherlands",
            "sc": "Seychelles", "fr": "France",
        }.get(
            (det.get("country") or "").lower(), (det.get("country") or "").upper(),
        ),
        "as": det.get("as") or "",
        "as_name": det.get("as_name") or "",
        "platform": det.get("platform") or "",
        "observed": format_mb_s(det.get("observed_bandwidth") or 0),
        "advertised": format_mb_s(det.get("advertised_bandwidth") or 0),
        "rate": format_mb_s(det.get("bandwidth_rate") or 0),
        "burst": format_mb_s(det.get("bandwidth_burst") or det.get("bandwidth_rate") or 0),
        "cw": det.get("consensus_weight") or 0,
        "cw_pct": f"{cw_frac * 100:.4f}%" if cw_frac else "N/A",
        "guard_pct": f"{guard_p * 100:.4f}%" if guard_p else "N/A",
        "middle_pct": f"{mid_p * 100:.4f}%" if mid_p else "N/A",
        "exit_pct": f"{exit_p * 100:.4f}%" if exit_p else "N/A",
        "family_n": len(det.get("effective_family") or []),
        "first_seen": det.get("first_seen") or "",
        "first_seen_ago": days_ago(det.get("first_seen"), published),
        "last_restarted": det.get("last_restarted") or "",
        "last_restarted_ago": days_ago(det.get("last_restarted"), published),
        "contact_short": (contact[:40] + "…") if len(contact) > 40 else contact,
        "aroi": aroi,
        "role_label": role_label,
        "running": bool(det.get("running")),
        "measured": det.get("measured"),
    }


PAGE_CSS = """
:root { --aeo-green:#00ff7f; --aeo-dark-surface:#1e1e1e; --aeo-text-muted:#ccc;
  --color-success:#28a745; --color-danger:#dc3545; --color-warning-text:#856404;
  --color-muted:#6c757d; --color-info:#17a2b8; --color-link:#337ab7;
  --color-bg-light:#f8f9fa; --color-text-dark:#495057; --color-text-heading:#2c3e50;
  --color-border-light:#dee2e6; --color-border-subtle:#e9ecef; --overload:#c0392b; }
* { box-sizing: border-box; }
body { margin:0; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size:14px; color:#333; background:#fff; }
a { color: var(--color-link); text-decoration:none; }
a:hover { text-decoration:underline; }
.aeo-cross-nav { background: var(--aeo-dark-surface); padding:10px 0; }
.aeo-nav-container { max-width:1120px; margin:0 auto; padding:0 16px;
  display:flex; justify-content:space-between; align-items:center; }
.aeo-nav-brand { color: var(--aeo-green); font-weight:bold; text-decoration:none; }
.aeo-nav-links a { color: var(--aeo-text-muted); margin-left:16px; text-decoration:none; }
.aeo-nav-links a.active { color: var(--aeo-green); }
.container { max-width:1120px; margin:0 auto; padding:12px 16px 40px; }
.page-title { font-size:28px; margin:12px 0 6px; color: var(--color-text-heading); }
.relay-meta { font-size:13px; color:#555; line-height:1.6; margin:0 0 12px; }
.breadcrumb { font-size:13px; color:#777; margin:0 0 8px; }
.option-banner { margin:8px 0 16px; padding:10px 14px; border-radius:6px;
  background:#eef6fb; border-left:4px solid #337ab7; font-size:13px; color:#1b3a4b; }
.option-banner strong { display:block; font-size:14px; margin-bottom:2px; }
.option-banner.recommend { background:#eef8f1; border-left-color:#009E73; }
.section-box { margin:20px 0; padding:15px; background: var(--color-bg-light); border-radius:8px; }
.section-box.recommend { background:#eef8f1; border-left:4px solid #009E73; }
.section-header { display:inline-block; }
.section-header a { color:inherit; text-decoration:none; }
h3 { font-size:16px; color: var(--color-text-heading); margin:24px 0 8px; }
h4 { margin-top:0; margin-bottom:12px; font-size:18px; }
.subsection-header { margin:0 0 10px; padding-bottom:6px; font-weight:600;
  font-size:15px; color: var(--color-text-dark); border-bottom:2px solid var(--color-border-light); }
.row { display:flex; flex-wrap:wrap; margin:0 -8px; }
.col { flex:1 1 300px; padding:0 8px; min-width:0; }
dl { margin:0; }
dt { font-weight:600; color:#555; font-size:13px; margin-top:8px; }
dd { margin:2px 0 0; }
.al-status-success { color: var(--color-success); }
.al-status-danger { color: var(--color-danger); }
.al-status-warning { color: var(--color-warning-text); }
.al-status-muted { color: var(--color-muted); }
.al-text-small-muted { font-size:12px; color: var(--color-muted); }
.health-status-grid { display:grid; grid-template-columns:1.2fr 1fr; gap:8px 24px; }
.health-row { display:flex; align-items:baseline; gap:10px; margin-bottom:6px; }
.health-row dt { margin:0; min-width:88px; }
.health-row dd { margin:0; }
.participation { margin-top:12px; padding:10px; background:#fff; border-radius:4px;
  border:1px solid var(--color-border-subtle); font-size:13px; }
.chart-wrap { margin:12px 0; background:#fff; border-radius:6px; padding:8px 8px 4px;
  border:1px solid var(--color-border-subtle); }
.chart-wrap img { width:100%; height:auto; display:block; }
.chart-note { font-size:12px; color:#666; margin:4px 8px 8px; }
.layout-label { margin:16px 0 8px; padding:8px 12px; background:#fff;
  border-left:3px solid #337ab7; font-size:13px; color:#1b3a4b; }
.layout-label strong { display:block; font-size:14px; margin-bottom:2px; }
.heading-row { display:flex; align-items:baseline; justify-content:space-between;
  gap:12px; flex-wrap:wrap; }
.overload-cue { color: var(--overload); font-size:13px; font-weight:600; }
.copy-table { border-collapse:collapse; width:100%; font-size:13px; }
.copy-table th, .copy-table td {
  border:1px solid var(--color-border-light); padding:6px 8px; text-align:left;
}
.copy-table th { background:#fff; color:#555; }
.ghost { opacity:0.45; }
.explain { font-size:12px; color:#555; margin-top:12px; padding:8px;
  background:#fff; border-radius:4px; border-left:3px solid #17a2b8; }
code { font-size:12px; background:#eee; padding:1px 4px; border-radius:3px; }
.aeo-footer { background: var(--aeo-dark-surface); color:#aaa; text-align:center;
  padding:18px 12px; font-size:12px; margin-top:24px; }
.aeo-footer a { color: var(--aeo-green); }
"""


def chart_block_html(nick, chart_file, note, label=None):
    label_html = (f'<div class="layout-label"><strong>{label}</strong></div>'
                  if label else "")
    return f"""{label_html}<div class="chart-wrap">
      <img src="{chart_file}" alt="Throughput history for {nick}">
      <p class="chart-note">{note}</p>
    </div>"""


def write_bandwidth_page_html(path, option, ctx, chart_file, overload_text=None,
                             heading_overload=None, charts=None, extra_html=""):
    """Write a static HTML mock of relay-info.html #bandwidth with one placement."""
    nick = ctx["nickname"]
    fp = ctx["fingerprint"]
    aroi = ctx["aroi"] or "unknown"
    family = ctx["family_n"] or 1
    heading_cue = heading_overload if heading_overload is not None else overload_text
    ov_html = (f'<span class="overload-cue">{heading_cue}</span>'
               if heading_cue else "")
    stability = ('<span class="al-status-danger">Overloaded</span>'
                 if overload_text else
                 '<span class="al-status-success">Not Overloaded</span>')
    default_note = (
        "Onionoo <code>write_history</code> / <code>read_history</code> "
        "· advertised is the descriptor snapshot, not a history."
    )
    if not charts:
        charts = [{"file": chart_file, "note": default_note}]
    chart = "".join(
        chart_block_html(nick, c["file"], c.get("note") or default_note,
                         c.get("label"))
        for c in charts
    )

    if option["id"] == 1:
        heading = f"""<div class="heading-row">
          <h4 style="margin:0;"><div class="section-header"><a href="#bandwidth">Bandwidth Metrics</a></div></h4>
          {ov_html}
        </div>"""
        body = f"""
        {chart}
        <div class="row">
          {capacity_col(ctx)}
          {measurement_col(ctx)}
        </div>
        {participation_box(ctx)}
        """
    elif option["id"] == 2:
        heading = """<h4><div class="section-header"><a href="#bandwidth">Bandwidth Metrics</a></div></h4>"""
        body = f"""
        <div class="row">
          {capacity_col(ctx)}
          {measurement_col(ctx)}
        </div>
        {chart}
        {participation_box(ctx)}
        """
    else:
        heading = """<h4><div class="section-header"><a href="#bandwidth">Bandwidth Metrics</a></div></h4>"""
        body = f"""
        <div class="row">
          {capacity_col(ctx)}
          {measurement_col(ctx)}
        </div>
        {participation_box(ctx)}
        <h5 class="subsection-header" style="margin-top:16px;">History
          <span class="al-text-small-muted">(Onionoo write / read)</span></h5>
        {extra_html}
        {chart}
        <div class="explain">
          <strong>Bandwidth Values Explained:</strong><br>
          <strong>Relay Reported</strong> = descriptor observed / advertised — flag eligibility.<br>
          <strong>Authority Measured</strong> = sbws — consensus weight.<br>
          <strong>This chart</strong> = bytes actually transferred (Onionoo /bandwidth),
          not observed_bandwidth over time.
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{nick} — Tor Relay | bandwidth chart layout option {option["id"]}</title>
  <style>{PAGE_CSS}</style>
</head>
<body>
<nav class="aeo-cross-nav"><div class="aeo-nav-container">
  <a class="aeo-nav-brand" href="#">1AEO</a>
  <div class="aeo-nav-links">
    <a href="#">Home</a><a class="active" href="#">Metrics</a>
    <a href="#">AROI Validator</a><a href="#">RouteFluxMap</a>
  </div>
</div></nav>
<div class="container">
  <p class="breadcrumb">Home &gt; Browse by Network &gt; {ctx["as"]} &gt; {nick}</p>
  <div class="option-banner">
    <strong>Option {option["id"]} of 3 — {option["name"]}</strong>
    {option["blurb"]}
    Relay: <strong>{nick}</strong> ({"1aeo family" if aroi=="1aeo.com" else aroi})
    · {"overloaded" if overload_text else "not overloaded"}.
  </div>
  <h1 class="page-title">View Relay "{nick}"</h1>
  <p class="relay-meta">
    Fingerprint: <code>{fp}</code> |
    Operator: <a href="#">{aroi}</a> |
    Family: {family} relay{"s" if family != 1 else ""} |
    {ctx["as"]} · {ctx["country_name"]} |
    {ctx["platform"]}
  </p>

  <div id="status" class="section-box" style="border-left:4px solid #28a745;">
    <h4><div class="section-header"><a href="#status">Health Status</a></div></h4>
    <div class="health-status-grid">
      <dl>
        <div class="health-row"><dt><a href="#flags">Consensus</a></dt>
          <dd><span class="al-status-success">In Consensus</span></dd></div>
        <div class="health-row"><dt><a href="#flags">Flags</a></dt>
          <dd>{ctx["flag_str"]}</dd></div>
        <div class="health-row"><dt><a href="#bandwidth">BW Verified</a></dt>
          <dd><span class="al-status-success">Measured</span></dd></div>
        <div class="health-row"><dt><a href="#uptime">Stability</a></dt>
          <dd>{stability} <span class="al-status-muted">|</span>
          <span class="al-status-success">{ctx["last_restarted_ago"]}</span></dd></div>
      </dl>
      <dl>
        <div class="health-row"><dt><a href="#connectivity">Reachability</a></dt>
          <dd>IPv4 / IPv6 <span class="al-text-small-muted">(Directory Auths)</span></dd></div>
        <div class="health-row"><dt><a href="#uptime">First Seen</a></dt>
          <dd>{ctx["first_seen_ago"]}</dd></div>
        <div class="health-row"><dt><a href="#bandwidth">BW Weight</a></dt>
          <dd>{ctx["cw_pct"]} of Network | {ctx["observed"]} Observed By Relay</dd></div>
        <div class="health-row"><dt>Version</dt>
          <dd><span class="al-status-success">0.4.9.11 Recommended</span></dd></div>
      </dl>
    </div>
  </div>

  <section id="flags" class="section-box ghost">
    <h4>Flags and Eligibility</h4>
    <p class="al-text-small-muted">Unchanged — eligibility table stays. Flag-flapping
    chart (R3) would sit here later. Dimmed in this mockup.</p>
  </section>

  <section id="bandwidth" class="section-box">
    {heading}
    {body}
  </section>

  <section id="uptime" class="section-box ghost">
    <h4>Uptime and Stability</h4>
    <p class="al-text-small-muted">Existing 1M/6M/1Y/5Y scalars + overload subsection
    stay. R1 uptime chart sits here. Dimmed in this mockup.
    Overload <em>details</em> remain in this section; the bandwidth chart only
    repeats a current cue if the flag is on.</p>
  </section>
</div>
<footer class="aeo-footer">
  Mockup of <code>relay-info.html</code> #bandwidth · Allium · Onionoo snapshot
  · not a live page
</footer>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path


def capacity_col(ctx):
    return f"""<div class="col">
      <h5 class="subsection-header">Capacity (Relay Reported)</h5>
      <dl>
        <dt>Observed Bandwidth</dt><dd>{ctx["observed"]}</dd>
        <dt>Advertised Bandwidth</dt><dd>{ctx["advertised"]}</dd>
        <dt>Rate Limit</dt><dd>{ctx["rate"]}</dd>
        <dt>Burst Limit</dt><dd>{ctx["burst"]}</dd>
      </dl>
    </div>"""


def measurement_col(ctx):
    return f"""<div class="col">
      <h5 class="subsection-header">Measurement (Directory Authority Verified)</h5>
      <dl>
        <dt>Measured By</dt>
        <dd><span class="al-status-success">Yes</span> (≥3 authorities)</dd>
        <dt>Consensus Weight</dt>
        <dd>{ctx["cw"]:,} <span class="al-text-small-muted">({ctx["cw_pct"]} of network)</span></dd>
      </dl>
    </div>"""


def participation_box(ctx):
    return f"""<div class="participation">
      <strong>Network Participation:</strong>
      Consensus Weight: {ctx["cw_pct"]} of network |
      Guard: {ctx["guard_pct"]} |
      Middle: {ctx["middle_pct"]} |
      Exit: {ctx["exit_pct"]}
    </div>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--details", default="/tmp/onionoo/details.json")
    parser.add_argument("--uptime", default="/tmp/onionoo/uptime_examples.json")
    parser.add_argument("--bandwidth", default="/tmp/onionoo/bandwidth_examples.json")
    parser.add_argument("--bandwidth-all", default="/tmp/onionoo/bandwidth_all.json")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "mockups"))
    parser.add_argument("--artifacts", default="/opt/cursor/artifacts")
    parser.add_argument(
        "--only", choices=("all", "bandwidth", "uptime", "flags", "bandcopy",
                           "chrome", "legends", "outcomes"),
        default="all",
        help="Skip unrelated mockup families when iterating on one chart.",
    )
    args = parser.parse_args()

    style()
    details = json.loads(Path(args.details).read_text())
    published = details.get("relays_published", "unknown")
    det = by_fp(details)
    up_doc = by_fp(json.loads(Path(args.uptime).read_text()))
    bw_doc = by_fp(json.loads(Path(args.bandwidth).read_text()))

    th4r_up = up_doc[TH4R]
    th4r_det = det[TH4R]
    ts, vals = history_series((th4r_up.get("uptime") or {}).get("1_month"))
    pct = as_pct(vals)

    def flag_avg(name):
        block = ((th4r_up.get("flags") or {}).get(name) or {}).get("1_month") or {}
        raw = [v for v in block.get("values") or [] if v is not None]
        if not raw:
            return 0.0
        return (sum(raw) / len(raw)) * (100.0 / 999.0)

    extra = {
        "last_restarted": th4r_det.get("last_restarted", "unknown"),
        "hsdir_1m": flag_avg("HSDir"),
        "guard_1m": flag_avg("Guard"),
    }
    th4r_periods = load_uptime_periods(th4r_up)
    f3_periods = load_uptime_periods(up_doc[F3NETZE])
    pirate_periods = load_uptime_periods(up_doc[PIRATE]) if PIRATE in up_doc else {}

    f3 = det[F3NETZE]
    f3_bw = bw_doc[F3NETZE]
    w_ts, w_vals = history_series((f3_bw.get("write_history") or {}).get("1_month"))
    r_ts, r_vals = history_series((f3_bw.get("read_history") or {}).get("1_month"))
    write_m = bytes_to_mbit(w_vals)
    read_m = bytes_to_mbit(r_vals)
    advertised_mbit = (f3.get("advertised_bandwidth") or 0) * 8.0 / 1_000_000.0
    # Onionoo only ships last_restarted (27 Jul). Extra dates mock a
    # restart archive so 6M/1Y/5Y can show a comma-delimited legend.
    events = restart_events(f3, extra=[
        "2026-03-18 04:00:00",
        "2025-10-09 12:00:00",
    ])
    # Merge /bandwidth overload fields when present (F3Netze snapshot has none).
    f3_ov = dict(f3)
    if f3_bw.get("overload_ratelimits"):
        f3_ov["overload_ratelimits"] = f3_bw["overload_ratelimits"]
    if f3_bw.get("overload_fd_exhausted"):
        f3_ov["overload_fd_exhausted"] = f3_bw["overload_fd_exhausted"]
    ov_status = overload_now_status(f3_ov, published)

    flag_names = ["Running", "Guard", "Stable", "Fast", "V2Dir", "HSDir"]
    flag_series = {}
    flags_block = th4r_up.get("flags") or {}
    for name in flag_names:
        fts, fvals = history_series((flags_block.get(name) or {}).get("1_month"))
        if fts:
            flag_series[name] = (fts, as_pct(fvals))
    flag_core = {k: flag_series[k] for k in ("Running", "Guard", "Stable", "HSDir")
                 if k in flag_series}

    overlays = load_ratio_overlays()
    overlays["bands"] = bands_for_flags(f3.get("flags"))
    out = Path(args.out)
    art = Path(args.artifacts)
    if args.only == "bandcopy":
        bw_all = dict(bw_doc)
        bw_all_path = Path(args.bandwidth_all)
        if bw_all_path.exists():
            bw_all.update(by_fp(json.loads(bw_all_path.read_text())))
        left = collect_band_copy_relay(
            f3, bw_all.get(F3NETZE) or f3_bw, list(det.values()),
            bw_all, published, "Exit+Guard",
        )
        jg = det.get(JEANGRAE)
        right = collect_band_copy_relay(
            jg, bw_all.get(JEANGRAE), list(det.values()),
            bw_all, published, "Guard",
        ) if jg else None
        if left and right:
            write_band_copy_proposals(left, right, published, out, art)
        else:
            print("skip bandcopy: missing F3Netze or jeangrae series")
        return
    if args.only == "chrome":
        bw_all = dict(bw_doc)
        bw_all_path = Path(args.bandwidth_all)
        if bw_all_path.exists():
            bw_all.update(by_fp(json.loads(bw_all_path.read_text())))
        write_chrome_style_gallery(
            det, bw_all, published, f3, f3_bw, overlays, ov_status,
            w_ts, read_m, write_m, advertised_mbit, events, out, art,
        )
        return
    if args.only == "legends":
        bw_all = dict(bw_doc)
        bw_all_path = Path(args.bandwidth_all)
        if bw_all_path.exists():
            bw_all.update(by_fp(json.loads(bw_all_path.read_text())))
        write_legend_subtitle_gallery(
            det, bw_all, published, f3, f3_bw, overlays, ov_status,
            w_ts, read_m, write_m, advertised_mbit, events, out, art,
        )
        return
    if args.only == "outcomes":
        bw_all = dict(bw_doc)
        bw_all_path = Path(args.bandwidth_all)
        if bw_all_path.exists():
            bw_all.update(by_fp(json.loads(bw_all_path.read_text())))
        write_outcome_subtitle_gallery(
            det, bw_all, published, f3, f3_bw, overlays, ov_status,
            w_ts, read_m, write_m, advertised_mbit, events, out, art,
        )
        return
    jobs = []
    if args.only in ("all", "uptime"):
        jobs.extend([
            ("relay_uptime_a_annotated_line.png", uptime_a_annotated_line, (ts, pct, published)),
            ("relay_uptime_b_area_threshold.png", uptime_b_area_threshold, (ts, pct, published, extra)),
            ("relay_uptime_c_heatmap.png", uptime_c_heatmap, (ts, pct, published, extra)),
            ("relay_uptime_section_numbers.png", uptime_section_numbers, (ts, pct, published, extra)),
            ("relay_uptime_b_two_clocks_th4r.png", uptime_b_two_clocks,
             (ts, pct, published, extra["last_restarted"], "th4r")),
            ("relay_uptime_b_two_clocks_f3.png", uptime_b_two_clocks,
             (*f3_periods["1_month"], published, f3.get("last_restarted"), "F3Netze")),
            ("relay_uptime_onionoo_info.png", uptime_onionoo_info, (published,)),
            ("relay_uptime_periods_pills_th4r.png", uptime_periods_pills,
             (th4r_periods, "1_month", "th4r", published,
              "Question: how do we switch 1M / 6M / 1Y / 5Y on a static page? "
              "CSS pills, one SVG visible. th4r has 1M/6M/1Y. Onionoo omitted "
              "5_years (first seen Oct 2025) — no 0% tab. Default 1M. "
              "C heatmap stays 1-month-only.")),
            ("relay_uptime_periods_pills_f3_5y.png", uptime_periods_pills,
             (f3_periods, "5_years", "F3Netze", published,
              "Question: why include 5Y at all? F3Netze 1M is 99.2% (looks fine). "
              "5Y average is 89% with real zeros. The long graph is the one that "
              "changes the story. Same B encoding; only the series and bucket "
              "size change.")),
            ("relay_uptime_periods_pills_young.png", uptime_periods_pills,
             (pirate_periods, "1_month", "PirateyMatey", published,
              "Question: what if Onionoo only published 1_month? Show that pill "
              "alone. 16 four-hour points (first seen 12 Aug) — say “not enough "
              "history for 6M/1Y/5Y”, do not invent 0% periods. "
              "Allium's count<30 → 0.0 trap must not become a chart.")),
            ("relay_uptime_periods_multiples.png", uptime_periods_multiples,
             (f3_periods, "F3Netze", published)),
            ("relay_uptime_periods_hero_sparks.png", uptime_periods_hero_sparks,
             (f3_periods, "F3Netze", published)),
        ])
    if args.only in ("all", "bandwidth"):
        jobs.extend([
            ("relay_bandwidth_a_dual_line.png", bandwidth_a_dual_line,
             (w_ts, read_m, write_m, advertised_mbit, events, published, overlays,
              ov_status)),
            ("relay_bandwidth_b_area_ratio.png", bandwidth_b_area_ratio,
             (w_ts, read_m, write_m, advertised_mbit, events, published, overlays,
              ov_status)),
            ("relay_bandwidth_c_bars_advertised.png", bandwidth_c_bars_advertised,
             (w_ts, read_m, write_m, advertised_mbit, events, published, ov_status)),
        ])
    if args.only in ("all", "flags"):
        jobs.extend([
            ("relay_flags_a_swimlane.png", flags_a_swimlane, (flag_core, published)),
            ("relay_flags_b_overlay.png", flags_b_overlay, (flag_core, published)),
            ("relay_flags_c_cause_effect.png", flags_c_cause_effect,
             (flag_series, published, extra)),
            ("relay_flags_d_episodes.png", flags_d_episodes,
             (flag_series, published, extra)),
            ("relay_flags_e_diverged_only.png", flags_e_diverged_only,
             (flag_series, published, extra)),
            ("relay_flags_f_status_story.png", flags_f_status_story,
             (flag_series, published, extra)),
        ])
    for name, fn, fn_args in jobs:
        fn(*fn_args, [out / name, art / name])
        print("wrote", name)

    if args.only in ("all", "bandwidth"):
        write_page_layout_mockups(
            det, bw_doc, Path(args.bandwidth_all), published, overlays,
            w_ts, read_m, write_m, advertised_mbit, events, ov_status,
            out, art,
        )


def plot_role_band_geometry(out_paths):
    """Four frozen flag-set bands. 1.20 is investigate for Exit, not Guard."""
    catalog = load_role_bands()
    fig, ax = plt.subplots(figsize=(11.0, 5.4))
    roles = ("Exit", "Exit+Guard", "Guard", "Middle")
    ax.axvspan(0.70, 1.90, color=BAD, alpha=0.06)
    ax.axvline(1.0, color=GREEN, linestyle="--", linewidth=1.0)
    ax.axvline(1.20, color=NAVY, linestyle=":", linewidth=1.3)
    ax.annotate(
        "1.20  ·  Exit p98.7 (investigate)\n"
        "Guard p91.6 (uncommon)",
        xy=(1.20, 3.45), xytext=(1.42, 3.55),
        fontsize=8, color=NAVY,
        arrowprops=dict(arrowstyle="->", color=NAVY),
        bbox=dict(boxstyle="round,pad=0.3", fc="#f7f7f7", ec="#dddddd"),
    )
    for i, role in enumerate(roles):
        b = catalog["roles"][role]
        y = len(roles) - 1 - i
        ax.barh(y, b["invest_hi"] - b["invest_lo"], left=b["invest_lo"],
                height=0.52, color=AMBER, alpha=0.35, zorder=1)
        ax.barh(y, b["typical_hi"] - b["typical_lo"], left=b["typical_lo"],
                height=0.52, color=GREEN, alpha=0.7, zorder=2)
        ax.plot([b["invest_lo"], b["invest_lo"]], [y - 0.32, y + 0.32],
                color=BAD, lw=1.6, zorder=3)
        ax.plot([b["invest_hi"], b["invest_hi"]], [y - 0.32, y + 0.32],
                color=BAD, lw=1.6, zorder=3)
        ax.text(0.705, y, f"{role}  n={b['n']}", va="center", ha="left",
                fontsize=8.5, fontweight="bold", color=NAVY)
        ax.text(
            1.73, y,
            f"typical p10–p90  {b['typical_lo']:.2f}–{b['typical_hi']:.2f}"
            f"   investigate >p98  {b['invest_hi']:.2f}",
            va="center", ha="left", fontsize=7.5, color=GRAY,
        )
    ax.set_yticks([])
    ax.set_xlim(0.70, 2.15)
    ax.set_ylim(-0.6, 4.1)
    ax.set_xlabel("Write / read  (frozen 1-month month-mean, ≥50 KB/s)")
    ax.set_title("Role-specific bands  ·  typical = this flag set’s p10–p90  ·  "
                 "investigate = beyond this flag set’s p98")
    fig.text(
        0.01, 0.01,
        "Frozen from Onionoo 2026-08-15 19:00 UTC. Do not recompute live — "
        "a DoS that hits every Exit would move p10–p90 and hide itself. "
        "The role-median overlay on the relay chart is the confirmation, "
        "not a second set of bands.",
        fontsize=8, color=GRAY,
    )
    fig.subplots_adjust(bottom=0.16, right=0.98)
    save(fig, out_paths)


def plot_dos_frozen_vs_live(det, bw_by_fp, out_paths, shift=0.25):
    """A network-wide Exit DoS: frozen bands still alarm; live p10–p90 hide it."""
    month = []
    for r in det.values():
        if role_of(r.get("flags")) != "Exit":
            continue
        doc = bw_by_fp.get(r["fingerprint"])
        if not doc:
            continue
        w = history_map((doc.get("write_history") or {}).get("1_month"))
        rd = history_map((doc.get("read_history") or {}).get("1_month"))
        keys = [t for t in w if t in rd and rd[t] > 0]
        if len(keys) < 3:
            continue
        sw = sum(w[t] for t in keys)
        sr = sum(rd[t] for t in keys)
        thru = (sw + sr) / (2 * len(keys))
        if thru < 50_000:
            continue
        month.append(sw / sr)
    if len(month) < 50:
        print("skip DoS figure: not enough Exit ratios")
        return
    quiet = np.asarray(month, float)
    dos = quiet + shift
    bands = bands_for_flags(["Exit"])
    tlo, thi = bands["typical_lo"], bands["typical_hi"]
    ilo, ihi = bands["invest_lo"], bands["invest_hi"]
    live_lo, live_hi = np.percentile(dos, 10), np.percentile(dos, 90)

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.4), sharey=True)
    for ax, vals, title, lo, hi, kind in (
        (axes[0], dos,
         f"Frozen Exit bands  ·  typical {tlo:.2f}–{thi:.2f}",
         tlo, thi, "frozen"),
        (axes[1], dos,
         f"Live Exit p10–p90 of the DoS week  ·  {live_lo:.2f}–{live_hi:.2f}",
         live_lo, live_hi, "live"),
    ):
        clipped = vals[(vals >= 0.6) & (vals <= 1.8)]
        ax.hist(clipped, bins=40, color=BLUE, alpha=0.7, edgecolor="white")
        ax.axvspan(lo, hi, color=GREEN, alpha=0.20)
        ax.axvline(lo, color=GREEN, lw=1.2)
        ax.axvline(hi, color=GREEN, lw=1.2)
        if kind == "frozen":
            ax.axvline(ihi, color=BAD, lw=1.2)
        ax.axvline(1.0, color=GREEN, linestyle="--", lw=1.0)
        ax.set_xlim(0.70, 1.70)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Exit write / read  (month-mean + 0.25)")
        in_green = float(np.mean((vals >= lo) & (vals <= hi)))
        ax.text(
            0.04, 0.96,
            f"{in_green * 100:.0f}% of Exits fall in the green band",
            transform=ax.transAxes, va="top", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", fc="#f7f7f7", ec="#dddddd"),
        )
    axes[0].set_ylabel("Exits")
    # Fix the leftover text; annotate investigate on the frozen panel.
    axes[0].axvspan(ihi, 1.70, color=BAD, alpha=0.10)
    axes[0].text(0.04, 0.82, f"investigate >{ihi:.2f} (Exit p98)",
                 transform=axes[0].transAxes, fontsize=8, color=BAD)
    fig.suptitle(
        "DoS that hits every Exit (+0.25 write/read)  ·  "
        "frozen bands still fire  ·  live percentiles hide the event",
        fontsize=12, fontweight="bold",
    )
    fig.text(
        0.01, 0.01,
        "Quiet snapshot Exits shifted +0.25. Frozen typical is this role’s "
        "p10–p90 from 2026-08-15. Live p10–p90 is computed on the shifted "
        "week. The role-median overlay would also move — that is how you "
        "see “the whole role moved.” The band must not move with it.",
        fontsize=8, color=GRAY,
    )
    fig.subplots_adjust(bottom=0.16, top=0.82)
    save(fig, out_paths)


def _one_month_series(relay, bw_relay):
    w_ts, w_vals = history_series((bw_relay.get("write_history") or {}).get("1_month"))
    r_ts, r_vals = history_series((bw_relay.get("read_history") or {}).get("1_month"))
    if not w_ts or not r_ts:
        return None
    wmap = dict(zip(w_ts, w_vals))
    rmap = dict(zip(r_ts, r_vals))
    keys = sorted(set(wmap) & set(rmap))
    if len(keys) < 2:
        return None
    return {
        "ts": keys,
        "write_m": bytes_to_mbit([wmap[t] for t in keys]),
        "read_m": bytes_to_mbit([rmap[t] for t in keys]),
        "advertised_mbit": (relay.get("advertised_bandwidth") or 0) * 8.0 / 1_000_000.0,
        "events": restart_events(relay),
        "ov": None,  # filled by caller with published
    }


def collect_band_copy_relay(relay, doc, details_relays, bw_all, published, role):
    series = _one_month_series(relay, doc)
    if not series:
        return None
    family = set(relay.get("effective_family") or [])
    overlays = build_ratio_overlays(
        details_relays, bw_all, role, family_fps=family or None,
    )
    overlays["bands"] = bands_for_flags(relay.get("flags"))
    if family:
        overlays["operator_label"] = (
            f"Operator Family (median, n={overlays['family_n']})"
        )
    return {
        "nickname": relay.get("nickname") or role,
        "role": role,
        "series": series,
        "overlays": overlays,
        "ov": overload_now_status(relay, published),
    }


def plot_band_copy_pair(left, right, style, published, out_paths):
    """Stacked write/read strips: Exit+Guard on top, Guard below."""
    meta = BAND_COPY_META[style]
    fig, axes = plt.subplots(
        2, 1, figsize=(11.2, 7.4),
        gridspec_kw={"hspace": 0.34},
    )
    fig.subplots_adjust(top=0.88, bottom=0.12, left=0.09, right=0.70)
    fig.suptitle(meta["title"], fontsize=13, fontweight="bold")
    for ax, ctx in ((axes[0], left), (axes[1], right)):
        s = ctx["series"]
        _plot_ratio_strip(
            ax, s["ts"], s["read_m"], s["write_m"], s["events"],
            ctx["overlays"], bands=ctx["overlays"]["bands"],
            band_copy=style,
            title=f"{ctx['nickname']}  ·  {ctx['role']}",
            title_loc="left",
            title_fontsize=10,
            legend_loc="right",
        )
    caption(
        fig, published, meta["blurb"],
        footnote=(
            f"{census_footnote(left['overlays'].get('bands'))}  ·  "
            f"{census_footnote(right['overlays'].get('bands'))}"
        ),
    )
    save(fig, out_paths)


def plot_band_copy_cards(out_paths):
    """All five wordings as swatches — easier to compare than full strips."""
    eg = bands_for_flags(["Exit", "Guard"])
    guard = bands_for_flags(["Guard"])
    roles = [("Exit+Guard  ·  F3Netze", eg), ("Guard  ·  jeangrae", guard)]
    styles = list(BAND_COPY_STYLES)
    fig, axes = plt.subplots(
        len(styles), 2, figsize=(12.4, 11.2),
        gridspec_kw={"hspace": 0.08, "wspace": 0.08},
    )
    fig.subplots_adjust(top=0.93, bottom=0.04, left=0.04, right=0.98)
    fig.suptitle(
        "Typical / Uncommon / Investigate  ·  current vs aligned proposals",
        fontsize=13, fontweight="bold",
    )
    colors = (GREEN, AMBER, BAD)
    keys = ("typical", "uncommon", "investigate")
    for r, style in enumerate(styles):
        for c, (role_title, bands) in enumerate(roles):
            ax = axes[r][c]
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
            copy = band_legend_labels(bands, style)
            meta = BAND_COPY_META[style]
            if c == 0:
                ax.text(
                    0.0, 0.96, meta["short"], fontsize=9, fontweight="bold",
                    color=NAVY, va="top",
                )
            if r == 0:
                ax.text(
                    1.0, 0.96, role_title, fontsize=8.5, color=GRAY,
                    va="top", ha="right",
                )
            lines = []
            if copy.get("header"):
                lines.append((None, copy["header"]))
            for color, key in zip(colors, keys):
                lines.append((color, copy[key]))
            y = 0.72
            for color, text in lines:
                if color is None:
                    ax.text(0.02, y, text, fontsize=8, color=NAVY, va="center",
                            fontweight="bold")
                else:
                    ax.add_patch(plt.Rectangle(
                        (0.02, y - 0.07), 0.045, 0.12, facecolor=color,
                        edgecolor=color, alpha=0.45, transform=ax.transAxes,
                        clip_on=False,
                    ))
                    ax.text(0.09, y, text, fontsize=8, color="#222", va="center")
                y -= 0.22
            ax.add_patch(plt.Rectangle(
                (0.0, 0.02), 1.0, 0.86, fill=False, edgecolor="#dddddd",
                linewidth=0.8, transform=ax.transAxes, clip_on=False,
            ))
    save(fig, out_paths)


def write_band_copy_html(path, published, files):
    cards = []
    for style, fname in files:
        meta = BAND_COPY_META[style]
        cards.append(f"""
  <section class="section-box">
    <h4>{meta["title"]}</h4>
    <p class="relay-meta">{meta["blurb"]}</p>
    <div class="chart-wrap">
      <img src="{fname}" alt="{meta["title"]}">
    </div>
  </section>""")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Band-copy proposals · Typical / Uncommon / Investigate</title>
  <style>{PAGE_CSS}</style>
</head>
<body>
<nav class="aeo-cross-nav"><div class="aeo-nav-container">
  <a class="aeo-nav-brand" href="#">1AEO</a>
  <div class="aeo-nav-links">
    <a href="#">Home</a><a class="active" href="#">Metrics</a>
  </div>
</div></nav>
<div class="container">
  <div class="option-banner">
    <strong>Typical / Uncommon / Investigate — chosen copy</strong>
    Judgment + numeric range + percentile on every swatch. Role sits
    on the chart title. Census n is a footnote. Same frozen
    Exit+Guard (F3Netze) and Guard (jeangrae) 1-month series on every
    panel. Other wordings below are rejected alts.
  </div>
  <section class="section-box">
    <h4>Current field inventory</h4>
    <p class="relay-meta">
      Each swatch is built in <code>band_legend_labels()</code> from
      <code>data/role_ratio_bands.json</code>. Typical = p10–p90.
      Uncommon = p2–p10 and p90–p98. Investigate = outside p2–p98.
    </p>
    <table class="copy-table">
      <thead><tr>
        <th></th><th>Range</th><th>Role</th><th>Percentile</th><th>n</th>
      </tr></thead>
      <tbody>
        <tr><td>Typical</td><td>yes, a–b</td><td>yes</td>
          <td>p10–p90</td><td>yes</td></tr>
        <tr><td>Uncommon</td><td>yes, a–b / c–d</td><td>no</td>
          <td>no</td><td>no</td></tr>
        <tr><td>Investigate</td><td>yes, &lt;a or &gt;b</td><td>yes</td>
          <td>beyond p98</td><td>no</td></tr>
      </tbody>
    </table>
  </section>
  <section class="section-box">
    <h4>All wordings at a glance</h4>
    <div class="chart-wrap">
      <img src="relay_bandwidth_band_copy_cards.png"
           alt="Current and proposed band labels">
    </div>
  </section>
  {''.join(cards)}
  <p class="al-text-small-muted">Onionoo relays_published {published} UTC.
  Bands frozen from the 2026-08-15 19:00 census.</p>
</div>
<footer class="aeo-footer">
  Mockup of write/read band copy · Allium
</footer>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path


def write_band_copy_proposals(left, right, published, out, art):
    files = []
    plot_band_copy_cards(
        [out / "relay_bandwidth_band_copy_cards.png",
         art / "relay_bandwidth_band_copy_cards.png"],
    )
    print("wrote relay_bandwidth_band_copy_cards.png")
    for style in BAND_COPY_STYLES:
        name = f"relay_bandwidth_band_copy_{style}.png"
        plot_band_copy_pair(
            left, right, style, published, [out / name, art / name],
        )
        files.append((style, name))
        print("wrote", name)
    for dest in (out, art):
        write_band_copy_html(
            dest / "relay_page_bw_band_copy.html", published, files,
        )
    print("wrote relay_page_bw_band_copy.html")


def write_chrome_html(path, published, cards, f3_name):
    rows = []
    for card in cards:
        rec = ' recommend' if card.get("recommend") else ""
        badge = " · recommended" if card.get("recommend") else ""
        rows.append(f"""
  <section class="section-box{rec}">
    <h4>Style {card["id"]}  ·  {card["name"]}{badge}</h4>
    <p class="relay-meta">{card["blurb"]}</p>
    <div class="chart-wrap">
      <img src="{card["file"]}" alt="Style {card["id"]} {card["name"]}">
    </div>
  </section>""")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chart chrome · five light-theme styles</title>
  <style>{PAGE_CSS}</style>
</head>
<body>
<nav class="aeo-cross-nav"><div class="aeo-nav-container">
  <a class="aeo-nav-brand" href="#">1AEO</a>
  <div class="aeo-nav-links">
    <a href="#">Home</a><a class="active" href="#">Metrics</a>
  </div>
</div></nav>
<div class="container">
  <div class="option-banner recommend">
    <strong>Recommended: style 5 — despine, left titles, weights, method
    subtitle, one auto-callout</strong>
    Same levers as the 1AEO blog charts, on the light Allium page.
    Okabe–Ito stays. Do not paste the blog dark surface or
    <code>#00ff7f</code> onto every relay. The callout is built from
    the series (date + ratio) and is omitted when nothing is beyond
    this role’s p98.
  </div>
  <p class="relay-meta">
    Subject is <strong>jeangrae</strong> (Guard, 1aeo.com, family 241).
    22–23 Jul is off the 1.70 write/read scale — that is the one
    auto-callout. F3Netze at the bottom shows style 5 with no callout
    because that strip stays typical.
  </p>
  {''.join(rows)}
  <section class="section-box">
    <h4>Style 5 on F3Netze  ·  no callout when typical</h4>
    <p class="relay-meta">
      Same chrome. The auto-callout stays off because no 1-month day
      is beyond Exit+Guard p98. That is the point: do not invent a
      story on a quiet relay.
    </p>
    <div class="chart-wrap">
      <img src="{f3_name}" alt="Style 5 on F3Netze, no callout">
    </div>
  </section>
  <p class="al-text-small-muted">Onionoo relays_published {published} UTC.
  Light theme. Okabe–Ito series colors. Frozen bands from the
  2026-08-15 19:00 census.</p>
</div>
<footer class="aeo-footer">
  Mockup of chart chrome · Allium
</footer>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path


def write_chrome_style_gallery(det, bw_all, published, f3, f3_bw, f3_overlays,
                               f3_ov, f3_ts, f3_read, f3_write, f3_adv,
                               f3_events, out, art):
    """Five light-theme chrome styles on jeangrae, plus style 5 on F3."""
    jg = det.get(JEANGRAE)
    jg_doc = bw_all.get(JEANGRAE) if jg else None
    if not jg or not jg_doc:
        print("skip chrome: missing jeangrae series")
        return
    ctx = collect_band_copy_relay(
        jg, jg_doc, list(det.values()), bw_all, published, "Guard",
    )
    if not ctx:
        print("skip chrome: jeangrae has no 1M series")
        return
    s = ctx["series"]
    cards = []
    for key in CHROME_STYLE_ORDER:
        spec = chrome_spec(key)
        name = f"relay_bandwidth_chrome_{spec['id']}_{key}_jeangrae.png"
        bandwidth_a_dual_line(
            s["ts"], s["read_m"], s["write_m"], s["advertised_mbit"],
            s["events"], published, ctx["overlays"], ctx["ov"],
            [out / name, art / name],
            title="Throughput · last 30 days",
            overload_mode="title",
            page_ready=True,
            nickname="jeangrae",
            chrome=spec,
        )
        print("wrote", name)
        cards.append({
            "id": spec["id"],
            "name": spec["name"],
            "blurb": spec["blurb"],
            "file": name,
            "recommend": bool(spec.get("recommend")),
        })
    f3_name = "relay_bandwidth_chrome_5_callout_f3.png"
    bandwidth_a_dual_line(
        f3_ts, f3_read, f3_write, f3_adv, f3_events, published,
        f3_overlays, f3_ov, [out / f3_name, art / f3_name],
        title="Throughput · last 30 days",
        overload_mode="legend",
        page_ready=True,
        nickname="F3Netze",
        chrome=chrome_spec("callout"),
    )
    print("wrote", f3_name)
    for dest in (out, art):
        write_chrome_html(dest / "relay_page_bw_chrome.html", published,
                          cards, f3_name)
    print("wrote relay_page_bw_chrome.html")


def write_legend_subtitle_html(path, published, legend_cards, subtitle_cards,
                               f3_name):
    def cards_html(cards):
        rows = []
        for card in cards:
            rec = " recommend" if card.get("recommend") else ""
            badge = " · recommended" if card.get("recommend") else ""
            rows.append(f"""
  <section class="section-box{rec}">
    <h4>{card["name"]}{badge}</h4>
    <p class="relay-meta">{card["blurb"]}</p>
    <div class="chart-wrap">
      <img src="{card["file"]}" alt="{card["name"]}">
    </div>
  </section>""")
        return "".join(rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Legend attachment · subtitle copy</title>
  <style>{PAGE_CSS}</style>
</head>
<body>
<nav class="aeo-cross-nav"><div class="aeo-nav-container">
  <a class="aeo-nav-brand" href="#">1AEO</a>
  <div class="aeo-nav-links">
    <a href="#">Home</a><a class="active" href="#">Metrics</a>
  </div>
</div></nav>
<div class="container">
  <div class="option-banner recommend">
    <strong>Recommended: both keys under their panel · “Compared with
    other Guards”</strong>
    One attachment rule. The colored bands are other Guards, not a
    live ranking of this week. “Frozen quiet-census bands” is
    contributor jargon — it does not belong on the chart.
  </div>
  <p class="relay-meta">
    Style 5 chrome (despine, left titles, weights, callout). Subject is
    <strong>jeangrae</strong>. Legend mocks all use the recommended
    subtitle so the only change is where the keys sit.
  </p>
  <h3>Where the keys sit</h3>
  {cards_html(legend_cards)}
  <h3>Write/read subtitle copy</h3>
  <p class="relay-meta">
    All of these use both keys under their panel. The current line
    (“Frozen quiet-census bands …”) is option A — reject it.
  </p>
  {cards_html(subtitle_cards)}
  <section class="section-box recommend">
    <h4>Recommended combo on F3Netze</h4>
    <p class="relay-meta">
      Both keys under their panel. Overload still wraps onto a second
      legend line. No callout — the strip is typical. Subtitle says
      “other Exit+Guards.”
    </p>
    <div class="chart-wrap">
      <img src="{f3_name}" alt="Recommended legends and subtitle on F3Netze">
    </div>
  </section>
  <p class="al-text-small-muted">Onionoo relays_published {published} UTC.
  Light theme. Okabe–Ito. Bands from the 2026-08-15 19:00 snapshot.</p>
</div>
<footer class="aeo-footer">
  Mockup of legend attachment and subtitle copy · Allium
</footer>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path


def write_legend_subtitle_gallery(det, bw_all, published, f3, f3_bw,
                                  f3_overlays, f3_ov, f3_ts, f3_read,
                                  f3_write, f3_adv, f3_events, out, art):
    """Unified legends + subtitle copy on style 5."""
    jg = det.get(JEANGRAE)
    jg_doc = bw_all.get(JEANGRAE) if jg else None
    if not jg or not jg_doc:
        print("skip legends: missing jeangrae series")
        return
    ctx = collect_band_copy_relay(
        jg, jg_doc, list(det.values()), bw_all, published, "Guard",
    )
    if not ctx:
        print("skip legends: jeangrae has no 1M series")
        return
    s = ctx["series"]
    chrome = chrome_spec("callout")
    common = dict(
        title="Throughput · last 30 days",
        overload_mode="title",
        page_ready=True,
        nickname="jeangrae",
        chrome=chrome,
    )

    def draw(name, **extra):
        bandwidth_a_dual_line(
            s["ts"], s["read_m"], s["write_m"], s["advertised_mbit"],
            s["events"], published, ctx["overlays"], ctx["ov"],
            [out / name, art / name], **common, **extra,
        )
        print("wrote", name)

    legend_jobs = [
        (
            "split",
            "Current — one key on the plot, one under the dates",
            "Style 5 today. Throughput key sits in the empty band above "
            "advertised. Write/read key sits under the dates. Two "
            "patterns to learn.",
            "relay_bandwidth_legend_split_jeangrae.png",
            False,
        ),
        (
            "above",
            "Both keys at the top of their panel",
            "Throughput key stays in the shelf above advertised. "
            "Write/read gets a matching white shelf above 1.70 so the "
            "key is not on the bands or the triangles.",
            "relay_bandwidth_legend_top_jeangrae.png",
            False,
        ),
        (
            "below",
            "Both keys under their panel",
            "Ship this. Same rule on both strips: read the series, then "
            "the key under it. Throughput ylim tightens — no empty "
            "shelf. Write/read key stays off the triangles.",
            "relay_bandwidth_legend_bottom_jeangrae.png",
            True,
        ),
    ]
    legend_cards = []
    for attach, name, blurb, fname, rec in legend_jobs:
        draw(fname, legend_attach=attach, subtitle_style="peers")
        legend_cards.append({
            "name": name, "blurb": blurb, "file": fname, "recommend": rec,
        })

    subtitle_jobs = [
        (
            "jargon",
            "A — Frozen quiet-census bands",
            "Current line. Contributor shorthand for “we saved "
            "percentiles from one quiet snapshot and do not recompute "
            "them live.” Operators have no reason to know that.",
            "relay_bandwidth_subtitle_jargon_jeangrae.png",
            False,
        ),
        (
            "peers",
            "B — Compared with other Guards",
            "Ship this. Says who the colors compare against, and what "
            "typical / investigate mean, without “census” or “frozen.” "
            "The DoS reason stays in the docs.",
            "relay_bandwidth_legend_bottom_jeangrae.png",
            True,
        ),
        (
            "plain",
            "C — Green is usual / red is rare",
            "Plainest. Duplicates the legend swatches. Fine if we want "
            "the subtitle to stay short.",
            "relay_bandwidth_subtitle_plain_jeangrae.png",
            False,
        ),
        (
            "baseline",
            "D — Fixed baseline, not this week’s ranking",
            "Sneaks in “frozen” without the word. Useful if we ever "
            "need to hint at the DoS reason on-chart. Still a bit "
            "abstract.",
            "relay_bandwidth_subtitle_baseline_jeangrae.png",
            False,
        ),
        (
            "none",
            "E — No subtitle",
            "Title already says Guard. Legend already says typical / "
            "p10–p90. Cleanest chrome. Loses “compared with other "
            "Guards” for anyone who skips the legend.",
            "relay_bandwidth_subtitle_none_jeangrae.png",
            False,
        ),
    ]
    subtitle_cards = []
    for style, name, blurb, fname, rec in subtitle_jobs:
        if style != "peers":
            draw(fname, legend_attach="below", subtitle_style=style)
        subtitle_cards.append({
            "name": name, "blurb": blurb, "file": fname, "recommend": rec,
        })

    f3_name = "relay_bandwidth_legend_bottom_f3.png"
    bandwidth_a_dual_line(
        f3_ts, f3_read, f3_write, f3_adv, f3_events, published,
        f3_overlays, f3_ov, [out / f3_name, art / f3_name],
        title="Throughput · last 30 days",
        overload_mode="legend",
        page_ready=True,
        nickname="F3Netze",
        chrome=chrome,
        legend_attach="below",
        subtitle_style="peers",
    )
    print("wrote", f3_name)
    for dest in (out, art):
        write_legend_subtitle_html(
            dest / "relay_page_bw_legend_subtitle.html", published,
            legend_cards, subtitle_cards, f3_name,
        )
    print("wrote relay_page_bw_legend_subtitle.html")


# Operator-facing outcomes the two strips can conclude. C only.
# T / R are empty when history is thin or the month is all-clear.
OUTCOME_SCENARIOS = (
    {
        "id": "empty",
        "name": "Not enough history",
        "who": ("", ""),
    },
    {
        "id": "quiet",
        "name": "Quiet typical",
        "who": ("", ""),
    },
    {
        "id": "overload",
        "name": "Typical + currently overloaded",
        "who": ("", ""),
    },
    {
        "id": "restart",
        "name": "Typical + restart in the window",
        "who": ("", ""),
    },
    {
        "id": "uncommon",
        "name": "Uncommon month, no investigate day",
        "who": (
            "140 Mbit/s (22% of advertised)",
            "Write/read 1.21 · inside the Guard band with other Guards",
        ),
    },
    {
        "id": "spike_relay",
        "name": "Investigate spike · this relay only",
        "who": (
            "Write spiked · 98 Mbit/s (15% of advertised)",
            "Outside the Guard band 22–23 Jul · family and peers stayed",
        ),
    },
    {
        "id": "spike_family",
        "name": "Investigate spike · family moved, role stayed",
        "who": (
            "Write spiked · 220 Mbit/s (31% of advertised)",
            "Outside the Guard band with the family · other Guards stayed",
        ),
    },
    {
        "id": "spike_role",
        "name": "Investigate spike · the whole role moved",
        "who": (
            "Write spiked · 90 Mbit/s (18% of advertised)",
            "Outside the band with other Exits 8–9 Aug",
        ),
    },
    {
        "id": "persistent",
        "name": "Persistent investigate month",
        "who": (
            "60 Mbit/s (9% of advertised)",
            "Outside the Guard band · family and peers stayed",
        ),
    },
    {
        "id": "read_heavy",
        "name": "Read-heavy month",
        "who": (
            "80 Mbit/s (12% of advertised)",
            "Write/read 0.71 · inside the Guard band with other Guards",
        ),
    },
    {
        "id": "crash",
        "name": "Throughput crash",
        "who": (
            "Write and read both dropped · 18 Mbit/s (4% of advertised)",
            "",
        ),
    },
    {
        "id": "near",
        "name": "Near advertised",
        "who": ("", ""),
    },
    {
        "id": "both",
        "name": "Overloaded + investigate spike",
        "who": (
            "Write spiked · 300 Mbit/s (37% of advertised)",
            "Outside the Exit+Guard band 1 Aug · family and peers stayed",
        ),
    },
)


def _empty_cell(text):
    """Show a missing C subtitle as an em dash."""
    return text if text else "—"


def plot_outcome_scenario_cards(out_paths):
    """Compact C-only table: scenario · T · R."""
    n = len(OUTCOME_SCENARIOS)
    # One header row + n data rows in axes coords (row 0 is the header).
    rows = n + 1
    fig, ax = plt.subplots(figsize=(13.4, 0.72 + rows * 0.38))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, rows)
    ax.axis("off")
    fig.subplots_adjust(top=0.90, bottom=0.06, left=0.03, right=0.985)
    fig.text(
        0.03, 0.975,
        "Outcome subtitles  ·  C",
        fontsize=13, fontweight="bold", va="top",
    )
    fig.text(
        0.03, 0.935,
        "Empty (—) when history is thin or the month is all-clear. "
        "Spiked / dropped are bad. Uncommon months put write/read + "
        "inside the role band with peers. Investigate says Outside the band. "
        "Overload stays in the legend. Restart is a vertical line.",
        fontsize=8.2, color=GRAY, va="top",
    )
    cols = (
        (0.012, "Scenario", 0.23),
        (0.250, "T  throughput", 0.34),
        (0.600, "R  write/read", 0.39),
    )
    header_y = n
    ax.add_patch(plt.Rectangle(
        (0.0, header_y), 1.0, 1.0, facecolor="#1B3A4B",
        edgecolor="none", zorder=0,
    ))
    for x, label, _w in cols:
        ax.text(
            x, header_y + 0.50, label, fontsize=8.2, fontweight="bold",
            color="#ffffff", va="center", zorder=1,
        )
    for i, sc in enumerate(OUTCOME_SCENARIOS):
        y = n - 1 - i
        if i % 2 == 0:
            ax.add_patch(plt.Rectangle(
                (0.0, y), 1.0, 1.0, facecolor="#f4f6f7",
                edgecolor="none", zorder=0,
            ))
        t_line, r_line = sc["who"]
        values = (sc["name"], _empty_cell(t_line), _empty_cell(r_line))
        for (x, _label, _w), value in zip(cols, values):
            empty = value == "—"
            ax.text(
                x, y + 0.50, value, fontsize=8.0,
                fontweight="bold" if x < 0.05 else "normal",
                color="#9aa0a6" if empty else "#222",
                va="center", zorder=1,
            )
    fig.text(
        0.03, 0.018,
        "T = throughput strip  ·  R = write/read strip  ·  "
        "Nickname and operator sit above Throughput, not in the subtitle. "
        "No “this relay” / “still with” / “moved” / “Left.”",
        fontsize=7.4, color=GRAY, va="bottom",
    )
    save(fig, out_paths)


def write_outcome_html(path, published, cards, scenario_name, identity_cards=None):
    def block(card):
        return f"""
  <section class="section-box recommend">
    <h4>{card["name"]}</h4>
    <p class="relay-meta">{card["blurb"]}</p>
    <div class="chart-wrap">
      <img src="{card["file"]}" alt="{card["name"]}">
    </div>
  </section>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Outcome subtitles · C</title>
  <style>{PAGE_CSS}</style>
</head>
<body>
<nav class="aeo-cross-nav"><div class="aeo-nav-container">
  <a class="aeo-nav-brand" href="#">1AEO</a>
  <div class="aeo-nav-links">
    <a href="#">Home</a><a class="active" href="#">Metrics</a>
  </div>
</div></nav>
<div class="container">
  <div class="option-banner recommend">
    <strong>Locked: C</strong>
    Empty when history is thin or the month is all-clear (typical
    write/read, no investigate day, no spike, no crash). A write spike
    says <code>Write spiked</code> (bad / investigate). Both-fell says
    <code>Write and read both dropped</code>. Investigate / off-band
    says <code>Outside the Guard band</code>, not “Left.” Uncommon
    months put the write/read value on the same line as
    <code>inside the Guard band with other Guards</code>. Overload
    stays in the legend. Restart is a vertical line. Identity sits
    above Throughput at 13 pt bold:
    <code>jeangrae · 1aeo.com</code> then
    <code>Throughput · last 30 days · Guard</code>.
    Any advertised share is raw throughput plus percent:
    <code>99 Mbit/s (15% of advertised)</code>.
  </div>
  <p class="relay-meta">
    Legends match at 8 pt, both in a shelf at the top of the panel.
    Live subjects: <strong>jeangrae</strong> (spike, this relay only)
    and <strong>F3Netze</strong> (all-clear, currently overloaded).
  </p>
  <h3>Every story these two strips can conclude</h3>
  <div class="chart-wrap">
    <img src="{scenario_name}" alt="Outcome subtitle C table">
  </div>
  {''.join(block(c) for c in cards)}
  {('<h3>Where the name sits</h3>' + ''.join(block(c) for c in identity_cards)) if identity_cards else ''}
  <p class="al-text-small-muted">Onionoo relays_published {published} UTC.
  Light theme. Okabe–Ito. Both keys at the top. 8 pt legend text.</p>
</div>
<footer class="aeo-footer">
  Mockup of outcome subtitles · Allium
</footer>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path


def write_outcome_subtitle_gallery(det, bw_all, published, f3, f3_bw,
                                   f3_overlays, f3_ov, f3_ts, f3_read,
                                   f3_write, f3_adv, f3_events, out, art):
    """C outcome table plus live C charts on jeangrae and F3Netze."""
    jg = det.get(JEANGRAE)
    jg_doc = bw_all.get(JEANGRAE) if jg else None
    if not jg or not jg_doc:
        print("skip outcomes: missing jeangrae series")
        return
    ctx = collect_band_copy_relay(
        jg, jg_doc, list(det.values()), bw_all, published, "Guard",
    )
    if not ctx:
        print("skip outcomes: jeangrae has no 1M series")
        return
    s = ctx["series"]
    chrome = chrome_spec("callout")
    jg_op = operator_from_contact(jg.get("contact"))
    f3_op = operator_from_contact((f3 or {}).get("contact"))
    table_names = (
        "relay_bandwidth_outcome_c_table.png",
        "relay_bandwidth_outcome_scenarios.png",
    )
    plot_outcome_scenario_cards(
        [dest / name for dest in (out, art) for name in table_names],
    )
    print("wrote", table_names[0])

    live = (
        {
            "nick": "jeangrae",
            "operator": jg_op,
            "files": (
                "relay_bandwidth_outcome_c_jeangrae.png",
                "relay_bandwidth_outcome_who_jeangrae.png",
            ),
            "ts": s["ts"], "read_m": s["read_m"], "write_m": s["write_m"],
            "advertised_mbit": s["advertised_mbit"], "events": s["events"],
            "overlays": ctx["overlays"], "ov": ctx["ov"],
            "overload_mode": "title",
            "name": "jeangrae · C",
            "blurb": (
                "Write spiked. Outside the Guard band; family and peers "
                "stayed. Identity sits above Throughput: jeangrae · 1aeo.com. "
                "Throughput is raw plus percent of advertised."
            ),
        },
        {
            "nick": "F3Netze",
            "operator": f3_op,
            "files": (
                "relay_bandwidth_outcome_c_f3.png",
                "relay_bandwidth_outcome_who_f3.png",
            ),
            "ts": f3_ts, "read_m": f3_read, "write_m": f3_write,
            "advertised_mbit": f3_adv, "events": f3_events,
            "overlays": f3_overlays, "ov": f3_ov,
            "overload_mode": "legend",
            "name": "F3Netze · C",
            "blurb": (
                "All-clear month: typical write/read, no investigate day, "
                "no spike, no crash. Subtitles stay empty. Overload is the "
                "legend diamond. Identity sits above Throughput: "
                "F3Netze · f3netze.de."
            ),
        },
    )
    cards = []
    for spec in live:
        paths = [dest / name for dest in (out, art) for name in spec["files"]]
        bandwidth_a_dual_line(
            spec["ts"], spec["read_m"], spec["write_m"],
            spec["advertised_mbit"], spec["events"], published,
            spec["overlays"], spec["ov"], paths,
            title="Throughput · last 30 days",
            overload_mode=spec["overload_mode"],
            page_ready=True,
            nickname=spec["nick"],
            operator=spec["operator"],
            chrome=chrome,
            legend_attach="above",
            subtitle_style="who",
        )
        print("wrote", spec["files"][0])
        cards.append({
            "name": spec["name"],
            "blurb": spec["blurb"],
            "file": spec["files"][0],
        })

    # Refresh official style 5 to locked C copy + identity above Throughput.
    for dest_name, args in (
        ("relay_bandwidth_chrome_5_callout_jeangrae.png", dict(
            ts=s["ts"], read_m=s["read_m"], write_m=s["write_m"],
            advertised_mbit=s["advertised_mbit"], events=s["events"],
            overlays=ctx["overlays"], ov=ctx["ov"], nickname="jeangrae",
            operator=jg_op, overload_mode="title",
        )),
        ("relay_bandwidth_chrome_5_callout_f3.png", dict(
            ts=f3_ts, read_m=f3_read, write_m=f3_write,
            advertised_mbit=f3_adv, events=f3_events,
            overlays=f3_overlays, ov=f3_ov, nickname="F3Netze",
            operator=f3_op, overload_mode="legend",
        )),
    ):
        bandwidth_a_dual_line(
            args["ts"], args["read_m"], args["write_m"], args["advertised_mbit"],
            args["events"], published, args["overlays"], args["ov"],
            [out / dest_name, art / dest_name],
            title="Throughput · last 30 days",
            overload_mode=args["overload_mode"],
            page_ready=True,
            nickname=args["nickname"],
            operator=args["operator"],
            chrome=chrome,
            legend_attach="above",
            subtitle_style="who",
        )
        print("wrote", dest_name)

    identity_files = {
        "above": "relay_bandwidth_identity_above_jeangrae.png",
        "infront": "relay_bandwidth_identity_infront_jeangrae.png",
    }
    identity_cards = []
    for place, fname in identity_files.items():
        bandwidth_a_dual_line(
            s["ts"], s["read_m"], s["write_m"], s["advertised_mbit"],
            s["events"], published, ctx["overlays"], ctx["ov"],
            [out / fname, art / fname],
            title="Throughput · last 30 days",
            overload_mode="title",
            page_ready=True,
            nickname="jeangrae",
            operator=jg_op,
            identity_placement=place,
            chrome=chrome,
            legend_attach="above",
            subtitle_style="who",
        )
        print("wrote", fname)
        if place == "above":
            f3_above = "relay_bandwidth_identity_above_f3.png"
            bandwidth_a_dual_line(
                f3_ts, f3_read, f3_write, f3_adv, f3_events, published,
                f3_overlays, f3_ov, [out / f3_above, art / f3_above],
                title="Throughput · last 30 days",
                overload_mode="legend",
                page_ready=True,
                nickname="F3Netze",
                operator=f3_op,
                identity_placement="above",
                chrome=chrome,
                legend_attach="above",
                subtitle_style="who",
            )
            print("wrote", f3_above)
            identity_cards.append({
                "name": "Above Throughput · ship this",
                "blurb": (
                    "13 pt bold: jeangrae · 1aeo.com, tied with Throughput. "
                    "A real gap sits under the names. Metric title stays "
                    "short. A screenshot still names the relay."
                ),
                "file": fname,
            })
        else:
            identity_cards.append({
                "name": "In front of Throughput · rejected",
                "blurb": (
                    "jeangrae · 1aeo.com · Throughput · last 30 days · Guard "
                    "is one long line. It wraps and repeats the page heading "
                    "at title weight."
                ),
                "file": fname,
            })

    for dest in (out, art):
        write_outcome_html(
            dest / "relay_page_bw_outcomes.html", published,
            cards, "relay_bandwidth_outcome_c_table.png",
            identity_cards=identity_cards,
        )
    print("wrote relay_page_bw_outcomes.html")


def write_role_band_gallery_html(path, rows, published):
    """Option-C chrome with one History chart per frozen flag-set band."""
    cards = []
    for row in rows:
        ctx = row["ctx"]
        bands = row["bands"]
        cards.append(f"""
  <section class="section-box">
    <h4>{row["role"]}  ·  {ctx["nickname"]}</h4>
    <p class="relay-meta">
      <code>{ctx["fingerprint"]}</code> · {ctx["flag_str"]} · {ctx["as"]} ·
      {ctx["country_name"]} · family {ctx["family_n"]}<br>
      Frozen bands: typical {bands["typical_lo"]:.2f}–{bands["typical_hi"]:.2f}
      (p10–p90) · investigate &lt;{bands["invest_lo"]:.2f} or
      &gt;{bands["invest_hi"]:.2f} (beyond p98)
    </p>
    {chart_block_html(ctx["nickname"], row["chart"], row["note"])}
  </section>""")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Write/read bands by flag set · option C</title>
  <style>{PAGE_CSS}</style>
</head>
<body>
<nav class="aeo-cross-nav"><div class="aeo-nav-container">
  <a class="aeo-nav-brand" href="#">1AEO</a>
  <div class="aeo-nav-links">
    <a href="#">Home</a><a class="active" href="#">Metrics</a>
  </div>
</div></nav>
<div class="container">
  <div class="option-banner">
    <strong>Option C — one chart per frozen flag-set band</strong>
    Same History subsection as the F3Netze page. Each relay uses its own
    Exit / Guard / Exit+Guard / Middle p10–p90 and p98. Overlay is already
    on the strip.
  </div>
  {''.join(cards)}
  <p class="al-text-small-muted">Onionoo relays_published {published} UTC.
  Bands frozen from the 2026-08-15 19:00 census. Not a live percentile.</p>
</div>
<footer class="aeo-footer">
  Mockup of <code>relay-info.html</code> #bandwidth · Allium
</footer>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return path


def write_page_layout_mockups(det, bw_doc, bandwidth_all_path, published,
                              f3_overlays, w_ts, read_m, write_m,
                              advertised_mbit, events, ov_status, out, art):
    """Option C page chrome, period-layout variants, and one chart per role."""
    f3 = det[F3NETZE]
    f3_ctx = relay_page_context(f3, published, "Exit+Guard")
    ov_text = overload_quiet_text(ov_status)

    page_charts = [
        ("relay_bandwidth_page_opt1_hero_f3.png",
         dict(title="", overload_mode="none", page_ready=True, nickname="F3Netze")),
        ("relay_bandwidth_page_opt3_history_f3.png",
         dict(title="Throughput · last 30 days", overload_mode="legend",
              page_ready=True, nickname="F3Netze")),
    ]
    for name, kwargs in page_charts:
        bandwidth_a_dual_line(
            w_ts, read_m, write_m, advertised_mbit, events, published,
            f3_overlays, ov_status, [out / name, art / name], **kwargs,
        )
        print("wrote", name)

    bw_all = dict(bw_doc)
    if bandwidth_all_path.exists():
        print("loading", bandwidth_all_path)
        bw_all.update(by_fp(json.loads(bandwidth_all_path.read_text())))

    f3_periods = load_bandwidth_periods(bw_all.get(F3NETZE) or bw_doc[F3NETZE])
    period_jobs = [
        ("relay_bandwidth_periods_pills_f3.png", bandwidth_periods_pills,
         (f3_periods, "1_month", advertised_mbit, events, f3_overlays,
          ov_status, published, "F3Netze")),
        ("relay_bandwidth_periods_equal_f3.png", bandwidth_periods_equal,
         (f3_periods, advertised_mbit, events, ov_status, published, "F3Netze")),
        ("relay_bandwidth_periods_hero_sparks_f3.png",
         bandwidth_periods_hero_sparks,
         (f3_periods, advertised_mbit, events, f3_overlays, ov_status,
          published, "F3Netze")),
    ]
    for name, fn, fn_args in period_jobs:
        fn(*fn_args, [out / name, art / name], True)
        print("wrote", name)

    # Click-to-swap: one combined figure + one hero panel + one spark per period.
    for key in f3_periods:
        short = BW_PERIOD_META[key]["short"].lower()
        combo = f"relay_bandwidth_periods_hero_sparks_f3_{short}.png"
        bandwidth_periods_hero_sparks(
            f3_periods, advertised_mbit, events, f3_overlays, ov_status,
            published, "F3Netze", [out / combo, art / combo], True, key,
        )
        print("wrote", combo)
        hero_name = f"relay_bandwidth_hero_f3_{key}.png"
        block = f3_periods[key]
        bandwidth_a_dual_line(
            block["ts"], block["read_m"], block["write_m"], advertised_mbit,
            events, published, _period_overlays(f3_overlays, key), ov_status,
            [out / hero_name, art / hero_name],
            nickname="F3Netze",
            title=f"Throughput · {BW_PERIOD_META[key]['title']}  ·  {BW_PERIOD_META[key]['bucket']} buckets",
            overload_mode="legend", page_ready=True, period_key=key,
        )
        print("wrote", hero_name)
        spark_name = f"relay_bandwidth_spark_f3_{key}.png"
        save_period_spark(
            block, advertised_mbit, events, key,
            [out / spark_name, art / spark_name],
        )
        print("wrote", spark_name)
    for dest in (out, art):
        write_hero_sparks_swap_html(
            dest / "relay_bandwidth_hero_sparks_swap_f3.html",
            "F3Netze", f3_periods,
            lambda k: f"relay_bandwidth_hero_f3_{k}.png",
            lambda k: f"relay_bandwidth_spark_f3_{k}.png",
        )
    print("wrote relay_bandwidth_hero_sparks_swap_f3.html")

    th4r = det.get(TH4R)
    th4r_bw = bw_all.get(TH4R) or bw_doc.get(TH4R)
    if th4r and th4r_bw:
        th_periods = load_bandwidth_periods(th4r_bw)
        th_adv = (th4r.get("advertised_bandwidth") or 0) * 8.0 / 1_000_000.0
        th_events = restart_events(th4r)
        th_ov = overload_now_status(th4r, published)
        th_overlays = {"bands": bands_for_flags(th4r.get("flags"))}
        bandwidth_periods_pills(
            th_periods, "1_month", th_adv, th_events, th_overlays, th_ov,
            published, "th4r",
            [out / "relay_bandwidth_periods_pills_th4r.png",
             art / "relay_bandwidth_periods_pills_th4r.png"],
            page_ready=False,
        )
        print("wrote relay_bandwidth_periods_pills_th4r.png")

    role_specs = [
        (F3NETZE, "Exit+Guard", "relay_bandwidth_a_role_exitguard_f3.png"),
        (JEANGRAE, "Guard", "relay_bandwidth_a_role_guard_jeangrae.png"),
        (ZARATHUSTRA, "Exit", "relay_bandwidth_a_role_exit_zarathustra.png"),
        (TENDXX, "Middle", "relay_bandwidth_a_role_middle_10dxx.png"),
    ]
    gallery_rows = []
    jg_ctx = None
    band_copy_relays = {}
    for fp, role, name in role_specs:
        relay = det.get(fp)
        doc = bw_all.get(fp)
        if not relay or not doc:
            print("skip role chart", role, fp[:8])
            continue
        series = _one_month_series(relay, doc)
        if not series:
            print("skip role chart (no 1M)", role)
            continue
        ov = overload_now_status(relay, published)
        family = set(relay.get("effective_family") or [])
        print(f"computing {role} overlays for {relay.get('nickname')}")
        overlays = build_ratio_overlays(
            list(det.values()), bw_all, role, family_fps=family or None,
        )
        overlays["bands"] = bands_for_flags(relay.get("flags"))
        if role == "Guard" and family:
            overlays["operator_label"] = (
                f"Operator Family (median, n={overlays['family_n']})"
            )
        ctx = relay_page_context(relay, published, role)
        if fp == JEANGRAE:
            jg_ctx = ctx
            bandwidth_a_dual_line(
                series["ts"], series["read_m"], series["write_m"],
                series["advertised_mbit"], series["events"], published,
                overlays, ov,
                [out / "relay_bandwidth_a_jeangrae.png",
                 art / "relay_bandwidth_a_jeangrae.png"],
                nickname="jeangrae", overload_mode="title", page_ready=False,
            )
            bandwidth_a_dual_line(
                series["ts"], series["read_m"], series["write_m"],
                series["advertised_mbit"], series["events"], published,
                overlays, ov,
                [out / "relay_bandwidth_page_opt2_jeangrae.png",
                 art / "relay_bandwidth_page_opt2_jeangrae.png"],
                title="Throughput · last 30 days", overload_mode="title",
                page_ready=True, nickname="jeangrae",
            )
            print("wrote jeangrae option-2 charts")
        bandwidth_a_dual_line(
            series["ts"], series["read_m"], series["write_m"],
            series["advertised_mbit"], series["events"], published,
            overlays, ov, [out / name, art / name],
            nickname=relay.get("nickname") or role,
            overload_mode="legend" if ov else "title",
            page_ready=False,
        )
        print("wrote", name)
        wsum = float(np.sum(series["write_m"]))
        rsum = float(np.sum(series["read_m"]))
        mean_ratio = wsum / rsum if rsum else float("nan")
        gallery_rows.append({
            "role": role,
            "ctx": ctx,
            "bands": overlays["bands"],
            "chart": name,
            "note": (
                f"{role} frozen p10–p90 / beyond p98. "
                f"{ratio_zone_phrase(mean_ratio, overlays['bands'])}."
            ),
        })
        if fp in (F3NETZE, JEANGRAE):
            band_copy_relays[fp] = {
                "nickname": relay.get("nickname") or role,
                "role": role,
                "series": series,
                "overlays": overlays,
                "ov": ov,
            }

    options = [
        {
            "id": 1,
            "name": "Hero under the heading",
            "blurb": "Rejected alt. Chart is the first thing #bandwidth lands on.",
            "file": "relay_page_bw_opt1_hero_f3.html",
            "chart": "relay_bandwidth_page_opt1_hero_f3.png",
            "ctx": f3_ctx,
            "overload": ov_text,
            "heading_overload": ov_text,
        },
        {
            "id": 2,
            "name": "After Capacity / Measurement",
            "blurb": "Rejected alt. Scalars first, chart before Network Participation.",
            "file": "relay_page_bw_opt2_after_metrics_jeangrae.html",
            "chart": "relay_bandwidth_page_opt2_jeangrae.png",
            "ctx": jg_ctx or f3_ctx,
            "overload": None if jg_ctx else ov_text,
            "heading_overload": None,
        },
        {
            "id": 3,
            "name": "History subsection after Network Participation",
            "blurb": "Chosen. Snapshot numbers stay together. History is 1M hero "
                     "+ sparks; click a spark to swap it with the hero. Overload "
                     "sits on a second legend line, tight against Write/Read.",
            "file": "relay_page_bw_opt3_history_f3.html",
            "chart": "relay_bandwidth_page_opt3_history_f3.png",
            "ctx": f3_ctx,
            "overload": ov_text,
            "heading_overload": None,
            "extra_html": (
                '<div class="layout-label"><strong>Click a spark to swap it '
                'with the hero</strong></div>'
                '<iframe src="relay_bandwidth_hero_sparks_swap_f3.html" '
                'title="Hero plus sparks click to swap" '
                'style="width:100%;height:780px;border:1px solid #dee2e6;'
                'border-radius:6px;background:#fff;"></iframe>'
            ),
            "charts": [
                {
                    "label": "Default — 1M hero, 6M / 1Y / 5Y sparks",
                    "file": "relay_bandwidth_periods_hero_sparks_f3.png",
                    "note": "Click a spark (interactive frame above) to promote "
                            "it. 1M stays the default because it has the finest "
                            "buckets.",
                },
                {
                    "label": "After clicking the 6M spark",
                    "file": "relay_bandwidth_periods_hero_sparks_f3_6m.png",
                    "note": "6M is now the hero; 1M moved into the spark row. "
                            "Onionoo only publishes last_restarted (27 Jul). "
                            "18 Mar and 9 Oct on longer graphs are a mock of a "
                            "multi-restart archive — one legend, comma-delimited "
                            "dates, one vline each.",
                },
            ],
        },
    ]
    for opt in options:
        if opt["ctx"] is None:
            continue
        for dest in (out, art):
            write_bandwidth_page_html(
                dest / opt["file"], opt, opt["ctx"], opt["chart"],
                opt["overload"], heading_overload=opt.get("heading_overload"),
                charts=opt.get("charts"), extra_html=opt.get("extra_html") or "",
            )
        print("wrote", opt["file"])

    if gallery_rows:
        for dest in (out, art):
            write_role_band_gallery_html(
                dest / "relay_page_bw_opt3_role_bands.html",
                gallery_rows, published,
            )
        print("wrote relay_page_bw_opt3_role_bands.html")

    if F3NETZE in band_copy_relays and JEANGRAE in band_copy_relays:
        write_band_copy_proposals(
            band_copy_relays[F3NETZE], band_copy_relays[JEANGRAE],
            published, out, art,
        )

    plot_role_band_geometry(
        [out / "ratio_bands_by_role.png", art / "ratio_bands_by_role.png"],
    )
    print("wrote ratio_bands_by_role.png")
    plot_dos_frozen_vs_live(
        det, bw_all,
        [out / "ratio_bands_dos_frozen_vs_live.png",
         art / "ratio_bands_dos_frozen_vs_live.png"],
    )
    print("wrote ratio_bands_dos_frozen_vs_live.png")


if __name__ == "__main__":
    main()
