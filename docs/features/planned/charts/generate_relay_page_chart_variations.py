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
from matplotlib.colors import LinearSegmentedColormap

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

UPTIME_CMAP = LinearSegmentedColormap.from_list(
    "uptime", ["#8B1A1A", VERM, ORANGE, "#E8E07A", GREEN], N=256
)
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


def uptime_b_area_threshold(ts, pct, published, out_paths):
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    fig.subplots_adjust(bottom=0.20)
    arr = np.array(pct)
    ax.fill_between(ts, arr, 0, color=BLUE, alpha=0.18, linewidth=0)
    ax.plot(ts, pct, color=BLUE, linewidth=1.7, label="Running flag")
    below = arr < 95
    if below.any():
        ax.fill_between(
            ts, arr, 95, where=below, color=VERM, alpha=0.45,
            interpolate=True, label="Time below 95%",
        )
    ax.axhline(95, color=ORANGE, linestyle="--", linewidth=1.1,
               label="95% — WFU / Stable risk")
    ax.axhline(100, color=GREEN, linestyle=":", linewidth=1.0, alpha=0.8)
    ax.set_ylim(35, 104)
    ax.set_ylabel("Share of 4-hour window with Running (%)")
    ax.set_title("Uptime B — area + 95% threshold   ·   th4r (Guard, DE)")
    date_axis(ax)
    hours_below = int(below.sum()) * 4
    ax.legend(loc="lower left")
    caption(
        fig, published,
        f"Story: shade only the dangerous part. {int(below.sum())} four-hour "
        f"windows ({hours_below}h) sat below 95% — the region that eats Weighted "
        f"Fractional Uptime and can cost Stable / Guard / HSDir.",
    )
    save(fig, out_paths)


def uptime_c_heatmap(ts, pct, published, out_paths):
    hours = sorted({t.hour for t in ts})
    dates = sorted({t.date() for t in ts}, reverse=True)  # newest row on top
    mat = np.full((len(dates), len(hours)), np.nan)
    for t, v in zip(ts, pct):
        mat[dates.index(t.date()), hours.index(t.hour)] = v

    fig, ax = plt.subplots(figsize=(11.2, 6.4))
    fig.subplots_adjust(bottom=0.16)
    mesh = ax.imshow(
        mat, aspect="auto", cmap=UPTIME_CMAP, vmin=40, vmax=100,
        interpolation="nearest",
    )
    ax.set_xticks(range(len(hours)), [f"{h:02d}–{(h + 4) % 24:02d}" for h in hours])
    tick_idx = list(range(0, len(dates), 2))
    ax.set_yticks(tick_idx, [dates[i].strftime("%b %d") for i in tick_idx])
    ax.set_xlabel("UTC window (Onionoo 4-hour buckets)")
    ax.set_title("Uptime C — time-of-day heatmap   ·   th4r (Guard, DE)")
    ax.grid(False)
    for y, x in zip(*np.where(mat < 95)):
        ax.text(x, y, f"{mat[y, x]:.0f}", ha="center", va="center",
                fontsize=7, color="white", fontweight="bold")
    cbar = fig.colorbar(mesh, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Running %")
    caption(
        fig, published,
        "Story: are the gaps a nightly cron, or random? th4r's five dips sit at "
        "10:00 / 14:00 / 18:00 UTC — not a 04:00 restart job. A periodic pattern "
        "would light up one column.",
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
    ts, vals = history_series((th4r_up.get("uptime") or {}).get("1_month"))
    pct = as_pct(vals)

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
        ("relay_uptime_b_area_threshold.png", uptime_b_area_threshold, (ts, pct, published)),
        ("relay_uptime_c_heatmap.png", uptime_c_heatmap, (ts, pct, published)),
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
