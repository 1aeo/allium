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
import sys
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
# Frozen expected write/read range — not a live percentile.
# 400-relay 1_month sample (2026-08-15): p10–p90 was 0.97–1.12, median 1.02.
# A DoS that hits everyone would move a percentile band and hide the event.
RATIO_LO = 0.90
RATIO_HI = 1.15
TH4R = "27A06581F1CE22D1BA4D160F6E7C7AABAC176242"
F3NETZE = "3C89C80E2699FB6358BBB64FDC9547AFCB5C03F7"
PIRATE = "DD32947397C5E6A5FC0D6A6BBE5CD008DEC1A60B"

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
        "savefig.bbox": "tight",
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


def save(fig, paths):
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p)
    plt.close(fig)


def caption(fig, published, story, y=0.012):
    fig.text(
        0.01, y,
        f"{story}\nSource: Onionoo  ·  relays_published {published} UTC  ·  Allium relay-page mockup",
        fontsize=8, color=GRAY, va="bottom",
    )


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


def draw_event_lines(ax, events, x_values=None):
    """Restart is a point on the time axis. Overload is not drawn here.

    Onionoo has no overload history graph — only a last-detected timestamp —
    so overload is a current-status badge, not an x-axis range.
    """
    for ev in events:
        if ev["kind"] == "overload":
            continue
        x = event_x(ev["when"], x_values)
        ax.axvline(x, color=ev["color"], linestyle=ev["ls"], linewidth=1.8,
                   alpha=0.95, zorder=3)


def event_legend_handles(events):
    handles = []
    for ev in events:
        if ev["kind"] == "overload":
            continue
        handles.append(Line2D(
            [0], [0], color=ev["color"], linestyle=ev["ls"], linewidth=1.8,
            label=ev["legend"],
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


def draw_overload_badge(fig, status):
    """Current-status chip above the plot. Not a time-axis range."""
    if not status:
        return
    fig.text(
        0.99, 1.0, status["label"],
        ha="right", va="bottom",
        fontsize=8.5, color="white", fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.4", fc=OVERLOAD, ec=OVERLOAD),
    )


def load_ratio_overlays():
    path = Path(__file__).resolve().parent / "data" / "ratio_overlays.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())

    def as_series(rows):
        return {parse_onionoo_ts(t): v for t, v, _n in rows}

    return {
        "role": as_series(raw.get("exitguard_daily") or []),
        "role_label": "Exit+Guard peers  (network median)",
        "operator": as_series(raw.get("family_daily") or []),
        "operator_label": "This operator  (family median, n=24)",
        "family_outliers": raw.get("family_outliers", 0),
        "family_n": raw.get("family_n", 0),
    }


def overlay_values(ts, series):
    if not series:
        return None
    return [series.get(t, np.nan) for t in ts]


def ratio_legend_handles(overlays=None):
    handles = [
        Patch(facecolor=GREEN, alpha=0.22, edgecolor=GREEN,
              label=f"Expected  {RATIO_LO:.2f}–{RATIO_HI:.2f}  (fixed, not a percentile)"),
        Line2D([0], [0], color=NAVY, linewidth=1.6, label="This relay  write / read"),
        Patch(facecolor=BAD, alpha=0.16, edgecolor=BAD,
              label="Outside the expected range — unusual, usually something wrong"),
    ]
    overlays = overlays or {}
    if overlays.get("role"):
        handles.append(Line2D(
            [0], [0], color=SKY, linestyle="--", linewidth=1.4,
            label=overlays.get("role_label", "Role peers"),
        ))
    if overlays.get("operator"):
        handles.append(Line2D(
            [0], [0], color=GRAY, linestyle=":", linewidth=1.6,
            label=overlays.get("operator_label", "This operator"),
        ))
    return handles


def _plot_ratio_strip(axr, ts, read_m, write_m, events, overlays=None):
    overlays = overlays or {}
    ratio = np.array([w / r if r else np.nan for w, r in zip(write_m, read_m)])
    axr.axhspan(RATIO_LO, RATIO_HI, color=GREEN, alpha=0.16, zorder=0)
    axr.axhspan(0.45, RATIO_LO, color=BAD, alpha=0.07, zorder=0)
    axr.axhspan(RATIO_HI, 1.85, color=BAD, alpha=0.07, zorder=0)
    axr.axhline(1.0, color=GREEN, linestyle="--", linewidth=1.0, zorder=1)
    role = overlay_values(ts, overlays.get("role"))
    if role is not None:
        axr.plot(ts, role, color=SKY, linestyle="--", linewidth=1.4, zorder=2)
    op = overlay_values(ts, overlays.get("operator"))
    if op is not None:
        axr.plot(ts, op, color=GRAY, linestyle=":", linewidth=1.6, zorder=2)
    in_band = (ratio >= RATIO_LO) & (ratio <= RATIO_HI)
    if in_band.any():
        y = np.ma.masked_where(~in_band, ratio)
        axr.plot(ts, y, color=NAVY, linewidth=1.7, zorder=3)
    if (~in_band).any():
        y = np.ma.masked_where(in_band, ratio)
        axr.plot(ts, y, color=BAD, linewidth=2.0, zorder=4)
    draw_event_lines(axr, events)
    pad_xlim(axr, ts)
    axr.set_ylabel("Write / read")
    axr.set_ylim(0.50, 1.70)
    axr.legend(handles=ratio_legend_handles(overlays), loc="upper right",
               fontsize=7.5, frameon=True, fancybox=False, edgecolor="#dddddd")
    date_axis(axr)
    return float(np.nanmean(ratio))


def bandwidth_a_dual_line(ts, read_m, write_m, advertised_mbit, events, published,
                          overlays, overload_status, out_paths):
    fig, (ax, axr) = plt.subplots(
        2, 1, figsize=(11.2, 7.2), sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1.35], "hspace": 0.08},
    )
    fig.subplots_adjust(bottom=0.14)
    ax.plot(ts, write_m, color=WRITE, linewidth=1.8, label="Write (outbound)")
    ax.plot(ts, read_m, color=BLUE, linewidth=1.8, label="Read (inbound)")
    if advertised_mbit:
        ax.axhline(
            advertised_mbit, color=ORANGE, linestyle="--", linewidth=1.4,
            label=f"Advertised  {advertised_mbit:.0f} Mbit/s",
        )
    draw_event_lines(ax, events)
    pad_xlim(ax, ts)
    top = max([advertised_mbit or 0] + write_m + read_m)
    ax.set_ylim(0, top * 1.08)
    ax.set_ylabel("Throughput (Mbit/s)")
    ax.set_title("Bandwidth A — dual line + advertised + imbalance   ·   F3Netze")
    date_axis(ax)
    series = [
        Line2D([0], [0], color=WRITE, linewidth=1.8, label="Write (outbound)"),
        Line2D([0], [0], color=BLUE, linewidth=1.8, label="Read (inbound)"),
    ]
    if advertised_mbit:
        series.append(Line2D([0], [0], color=ORANGE, linestyle="--", linewidth=1.4,
                             label=f"Advertised  {advertised_mbit:.0f} Mbit/s"))
    ax.legend(handles=series + event_legend_handles(events),
              loc="upper left", fontsize=9, ncol=2)
    draw_overload_badge(fig, overload_status)

    mean_ratio = _plot_ratio_strip(axr, ts, read_m, write_m, events, overlays)
    used = 100.0 * np.mean(write_m) / advertised_mbit if advertised_mbit else 0
    fam_n = (overlays or {}).get("family_n") or 0
    fam_out = (overlays or {}).get("family_outliers") or 0
    caption(
        fig, published,
        f"Story: this relay mean write/read {mean_ratio:.2f}, inside the fixed "
        f"{RATIO_LO:.2f}–{RATIO_HI:.2f} expected range (not a live percentile — "
        f"a network DoS would move a percentile band and hide it). Exit+Guard "
        f"peers and this operator’s family median sit on top of it. "
        f"{fam_out} of {fam_n} family relays have a month-mean above 1.15; "
        f"this one does not. Delivered write ~{np.mean(write_m):.0f} Mbit/s "
        f"({used:.0f}% of advertised). Overload is a now-badge, not a time "
        f"range — Onionoo has no incident history.",
    )
    save(fig, out_paths)


def bandwidth_b_area_ratio(ts, read_m, write_m, advertised_mbit, events, published,
                           overlays, overload_status, out_paths):
    fig, (ax, axr) = plt.subplots(
        2, 1, figsize=(11.2, 7.0), sharex=True,
        gridspec_kw={"height_ratios": [3.1, 1.35], "hspace": 0.08},
    )
    fig.subplots_adjust(bottom=0.14)
    ax.fill_between(ts, write_m, color=WRITE, alpha=0.22, label="Write")
    ax.fill_between(ts, read_m, color=BLUE, alpha=0.22, label="Read")
    ax.plot(ts, write_m, color=WRITE, linewidth=1.2)
    ax.plot(ts, read_m, color=BLUE, linewidth=1.2)
    if advertised_mbit:
        ax.axhline(advertised_mbit, color=ORANGE, linestyle="--", linewidth=1.4,
                   label=f"Advertised  {advertised_mbit:.0f} Mbit/s")
    draw_event_lines(ax, events)
    pad_xlim(ax, ts)
    top = max([advertised_mbit or 0] + write_m + read_m)
    ax.set_ylim(0, top * 1.08)
    ax.set_ylabel("Throughput (Mbit/s)")
    ax.set_title("Bandwidth B — overlapping area + advertised + imbalance   ·   F3Netze")
    series = [
        Patch(facecolor=WRITE, alpha=0.35, label="Write"),
        Patch(facecolor=BLUE, alpha=0.35, label="Read"),
    ]
    if advertised_mbit:
        series.append(Line2D([0], [0], color=ORANGE, linestyle="--", linewidth=1.4,
                             label=f"Advertised  {advertised_mbit:.0f} Mbit/s"))
    ax.legend(handles=series + event_legend_handles(events),
              loc="upper left", fontsize=9, ncol=2)
    draw_overload_badge(fig, overload_status)
    _plot_ratio_strip(axr, ts, read_m, write_m, events, overlays)
    caption(
        fig, published,
        "Same restart marker, current-overload badge, fixed expected range, "
        "and role / operator overlays as A. Area fill is the alternate "
        "encoding; A is the preferred default.",
    )
    save(fig, out_paths)


def bandwidth_c_bars_advertised(ts, read_m, write_m, advertised_mbit, events,
                                published, overload_status, out_paths):
    fig, ax = plt.subplots(figsize=(11.2, 5.8))
    fig.subplots_adjust(bottom=0.18)
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
    ax.set_title("Bandwidth C — daily bars vs advertised   ·   F3Netze")
    tick = list(range(0, len(ts), 4))
    ax.set_xticks(tick, [ts[i].strftime("%b %d") for i in tick])
    series = [
        Patch(facecolor=WRITE, label="Write"),
        Patch(facecolor=BLUE, label="Read"),
    ]
    if advertised_mbit:
        series.append(Line2D([0], [0], color=ORANGE, linestyle="--", linewidth=1.4,
                             label=f"Advertised  {advertised_mbit:.0f} Mbit/s"))
    ax.legend(handles=series + event_legend_handles(events),
              loc="upper left", fontsize=9, ncol=2)
    draw_overload_badge(fig, overload_status)
    used = 100.0 * np.mean(write_m) / advertised_mbit if advertised_mbit else 0
    caption(
        fig, published,
        f"Story: this exit advertises {advertised_mbit:.0f} Mbit/s and delivers "
        f"~{np.mean(write_m):.0f} Mbit/s write ({used:.0f}% of advertised). "
        "Restart is a point. Overload is a current-status badge, not a time "
        "range — Onionoo has no incident history.",
    )
    save(fig, out_paths)


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--details", default="/tmp/onionoo/details.json")
    parser.add_argument("--uptime", default="/tmp/onionoo/uptime_examples.json")
    parser.add_argument("--bandwidth", default="/tmp/onionoo/bandwidth_examples.json")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "mockups"))
    parser.add_argument("--artifacts", default="/opt/cursor/artifacts")
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
    events = []
    if f3.get("last_restarted"):
        when = parse_onionoo_ts(f3["last_restarted"])
        events.append({
            "kind": "restart",
            "when": when,
            "color": RESTART,
            "ls": "-.",
            "legend": f"Last restarted  {when.strftime('%-d %b')}",
        })
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
    out = Path(args.out)
    art = Path(args.artifacts)
    jobs = [
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
        ("relay_bandwidth_a_dual_line.png", bandwidth_a_dual_line,
         (w_ts, read_m, write_m, advertised_mbit, events, published, overlays,
          ov_status)),
        ("relay_bandwidth_b_area_ratio.png", bandwidth_b_area_ratio,
         (w_ts, read_m, write_m, advertised_mbit, events, published, overlays,
          ov_status)),
        ("relay_bandwidth_c_bars_advertised.png", bandwidth_c_bars_advertised,
         (w_ts, read_m, write_m, advertised_mbit, events, published, ov_status)),
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
    ]
    for name, fn, fn_args in jobs:
        fn(*fn_args, [out / name, art / name])
        print("wrote", name)


if __name__ == "__main__":
    main()
