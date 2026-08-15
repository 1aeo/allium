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
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap

BLUE = "#0072B2"
VERM = "#D55E00"
GREEN = "#009E73"
SKY = "#56B4E9"
ORANGE = "#E69F00"
GRAY = "#666666"
NAVY = "#1B3A4B"
RED = "#C0392B"

TH4R = "27A06581F1CE22D1BA4D160F6E7C7AABAC176242"
F3NETZE = "3C89C80E2699FB6358BBB64FDC9547AFCB5C03F7"

FLAG_CMAP = LinearSegmentedColormap.from_list(
    "flag", ["#F4D6C9", ORANGE, GREEN], N=256
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
UPTIME_LEVEL_COLORS = ["#8B1A1A", VERM, ORANGE, "#E8E07A", GREEN]
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
        ax.plot(ts[a:b + 1], pct[a:b + 1], color=VERM, linewidth=2.4, zorder=4)
        ax.annotate(
            f"{ts[a].strftime('%b %d %H:%M')}\n{lo:.0f}% of 4h window",
            xy=(mid_t, lo),
            xytext=(0, -28 if i % 2 == 0 else -48),
            textcoords="offset points",
            ha="center", va="top", fontsize=7.5, color=VERM,
            arrowprops=dict(arrowstyle="-", color=VERM, lw=0.7),
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
            ts, arr, 98, where=below, color=VERM, alpha=0.40,
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
        ax.scatter([wt], [wv], s=42, color=VERM, zorder=5)
        ax.annotate(
            f"Worst bucket  {wv:.0f}%  once\n{fmt_window(wt)}\n"
            f"(2 of 4 hourly consensuses)",
            xy=(wt, wv), xytext=(18, -8), textcoords="offset points",
            fontsize=8, color=VERM,
            arrowprops=dict(arrowstyle="->", color=VERM, lw=0.8),
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


# ---------------------------------------------------------------------------
# Chart 6 — bandwidth variations (F3Netze, 1 month)
# ---------------------------------------------------------------------------

def bandwidth_a_dual_line(ts, read_m, write_m, events, published, out_paths):
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    fig.subplots_adjust(bottom=0.20)
    ax.plot(ts, write_m, color=VERM, linewidth=1.8, label="Write (outbound)")
    ax.plot(ts, read_m, color=BLUE, linewidth=1.8, label="Read (inbound)")
    _mark_events(ax, events, ymax=max(write_m + read_m) * 1.02)
    ax.set_ylabel("Throughput (Mbit/s)")
    ax.set_title("Bandwidth A — dual line   ·   F3Netze (Exit+Guard, DE)")
    date_axis(ax)
    ax.legend(loc="upper left")
    ratio = np.mean(write_m) / np.mean(read_m)
    caption(
        fig, published,
        f"Story: read and write track each other (mean write/read = {ratio:.2f}). "
        f"Forum 5–10× imbalance would show as two lines that refuse to overlap. "
        f"Vertical marks: last restart and current overload.",
    )
    save(fig, out_paths)


def bandwidth_b_area_ratio(ts, read_m, write_m, events, published, out_paths):
    fig, (ax, axr) = plt.subplots(
        2, 1, figsize=(11.2, 6.4), sharex=True,
        gridspec_kw={"height_ratios": [3.1, 1.15], "hspace": 0.08},
    )
    fig.subplots_adjust(bottom=0.16)
    ax.fill_between(ts, write_m, color=VERM, alpha=0.28, label="Write")
    ax.fill_between(ts, read_m, color=BLUE, alpha=0.28, label="Read")
    ax.plot(ts, write_m, color=VERM, linewidth=1.2)
    ax.plot(ts, read_m, color=BLUE, linewidth=1.2)
    _mark_events(ax, events, ymax=max(write_m + read_m) * 1.02)
    ax.set_ylabel("Throughput (Mbit/s)")
    ax.set_title("Bandwidth B — overlapping area + ratio strip   ·   F3Netze")
    ax.legend(loc="upper left", ncol=2)

    ratio = [w / r if r else np.nan for w, r in zip(write_m, read_m)]
    axr.plot(ts, ratio, color=NAVY, linewidth=1.5)
    axr.axhline(1.0, color=GREEN, linestyle="--", linewidth=1.0)
    axr.axhspan(0.8, 1.25, color=GREEN, alpha=0.10)
    axr.set_ylabel("Write / read")
    axr.set_ylim(0.6, 1.5)
    date_axis(axr)
    caption(
        fig, published,
        "Story: the ratio strip is the operator question. Stay inside the green "
        "band (0.8–1.25) and traffic is balanced. A 5× outbound spike would "
        "leave the band and stay there.",
    )
    save(fig, out_paths)


def bandwidth_c_bars_advertised(ts, read_m, write_m, advertised_mbit, events,
                                published, out_paths):
    fig, ax = plt.subplots(figsize=(11.2, 5.8))
    fig.subplots_adjust(bottom=0.20)
    x = np.arange(len(ts))
    w = 0.38
    ax.bar(x - w / 2, write_m, w, color=VERM, label="Write")
    ax.bar(x + w / 2, read_m, w, color=BLUE, label="Read")
    if advertised_mbit:
        ax.axhline(
            advertised_mbit, color=ORANGE, linestyle="--", linewidth=1.3,
            label=f"Advertised  {advertised_mbit:.0f} Mbit/s",
        )
    for label, when, color in events:
        if ts[0] <= when <= ts[-1]:
            # daily buckets: snap to nearest day
            idx = min(range(len(ts)), key=lambda i: abs(ts[i] - when))
            ax.axvline(idx, color=color, linestyle=":", linewidth=1.2, alpha=0.85)
            ax.text(idx + 0.3, advertised_mbit * 0.97 if advertised_mbit else max(write_m),
                    label, color=color, fontsize=8, rotation=90, va="top")
    ax.set_ylabel("Throughput (Mbit/s)")
    ax.set_title("Bandwidth C — daily bars vs advertised   ·   F3Netze")
    tick = list(range(0, len(ts), 4))
    ax.set_xticks(tick, [ts[i].strftime("%b %d") for i in tick])
    ax.set_xlim(-1, len(ts))
    ax.legend(loc="upper left", ncol=3)
    used = 100.0 * np.mean(write_m) / advertised_mbit if advertised_mbit else 0
    caption(
        fig, published,
        f"Story: this exit advertises {advertised_mbit:.0f} Mbit/s and delivers "
        f"~{np.mean(write_m):.0f} Mbit/s write ({used:.0f}% of advertised). "
        f"The '1 Gbps VPS, few MiB/s observed' complaint is a bar chart that "
        f"never approaches the dashed line.",
    )
    save(fig, out_paths)


def _mark_events(ax, events, ymax):
    for label, when, color in events:
        ax.axvline(when, color=color, linestyle=":", linewidth=1.2, alpha=0.9)
        ax.text(
            when, ymax, f"  {label}", color=color, fontsize=8,
            rotation=90, va="top", ha="left",
        )


# ---------------------------------------------------------------------------
# Extra relay-page chart — flag flapping (th4r)
# ---------------------------------------------------------------------------

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
            fill=False, edgecolor=VERM, linewidth=1.4,
        ))
    caption(
        fig, published,
        "Story: Running / Guard / Stable stay green. HSDir drops for days after "
        "each brief Running gap (Jul 19, Jul 30, Aug 11) and is still gone. "
        "Uptime scalars would say '99%'. This chart says why HSDir is missing.",
    )
    save(fig, out_paths)


def flags_b_overlay(flag_series, published, out_paths):
    colors = {
        "Running": BLUE,
        "Guard": GREEN,
        "Stable": ORANGE,
        "HSDir": VERM,
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
        "Story: same data as the swimlane. Overlay makes the HSDir divergence "
        "obvious, but overlapping 99% lines (Running/Guard/Stable) hide the "
        "small gaps that triggered the HSDir loss.",
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

    f3 = det[F3NETZE]
    f3_bw = bw_doc[F3NETZE]
    w_ts, w_vals = history_series((f3_bw.get("write_history") or {}).get("1_month"))
    r_ts, r_vals = history_series((f3_bw.get("read_history") or {}).get("1_month"))
    write_m = bytes_to_mbit(w_vals)
    read_m = bytes_to_mbit(r_vals)
    advertised_mbit = (f3.get("advertised_bandwidth") or 0) * 8.0 / 1_000_000.0
    events = []
    if f3.get("last_restarted"):
        events.append(("last restarted", parse_onionoo_ts(f3["last_restarted"]), NAVY))
    ov = parse_ms(f3.get("overload_general_timestamp"))
    if ov:
        events.append(("overload", ov, VERM))

    flag_names = ["Running", "Guard", "Stable", "HSDir"]
    flag_series = {}
    flags_block = th4r_up.get("flags") or {}
    for name in flag_names:
        fts, fvals = history_series((flags_block.get(name) or {}).get("1_month"))
        if fts:
            flag_series[name] = (fts, as_pct(fvals))

    out = Path(args.out)
    art = Path(args.artifacts)
    jobs = [
        ("relay_uptime_a_annotated_line.png", uptime_a_annotated_line, (ts, pct, published)),
        ("relay_uptime_b_area_threshold.png", uptime_b_area_threshold, (ts, pct, published, extra)),
        ("relay_uptime_c_heatmap.png", uptime_c_heatmap, (ts, pct, published, extra)),
        ("relay_uptime_section_numbers.png", uptime_section_numbers, (ts, pct, published, extra)),
        ("relay_bandwidth_a_dual_line.png", bandwidth_a_dual_line,
         (w_ts, read_m, write_m, events, published)),
        ("relay_bandwidth_b_area_ratio.png", bandwidth_b_area_ratio,
         (w_ts, read_m, write_m, events, published)),
        ("relay_bandwidth_c_bars_advertised.png", bandwidth_c_bars_advertised,
         (w_ts, read_m, write_m, advertised_mbit, events, published)),
        ("relay_flags_a_swimlane.png", flags_a_swimlane, (flag_series, published)),
        ("relay_flags_b_overlay.png", flags_b_overlay, (flag_series, published)),
    ]
    for name, fn, fn_args in jobs:
        fn(*fn_args, [out / name, art / name])
        print("wrote", name)


if __name__ == "__main__":
    main()
