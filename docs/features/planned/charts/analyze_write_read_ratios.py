#!/usr/bin/env python3
"""Survey write/read ratios from a full Onionoo /bandwidth dump.

Reads:
  /tmp/onionoo/bandwidth_all.json
  /tmp/onionoo/details.json

Writes JSON + PNG summaries under --out (default: this directory's data/ and mockups/).
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PERIODS = ("1_month", "6_months", "1_year", "5_years")
ROLES = ("Guard", "Exit+Guard", "Exit", "Middle")
CANDIDATE_BANDS = (
    (0.80, 1.25),
    (0.85, 1.20),
    (0.90, 1.15),
    (0.92, 1.12),
    (0.95, 1.10),
)
# Bytes/s mean (write+read)/2. Tiny relays make noisy ratios.
TRAFFIC_CUTS_BPS = (0, 10_000, 50_000, 100_000, 500_000)
PCTILES = (1, 5, 10, 25, 50, 75, 90, 95, 99)

BLUE = "#0072B2"
GREEN = "#009E73"
ORANGE = "#E69F00"
NAVY = "#1B3A4B"
GRAY = "#666666"
BAD = "#C0392B"


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


def parse_onionoo_ts(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def history_map(block):
    """Return {timestamp: bytes_per_sec} skipping nulls."""
    if not block or not block.get("values"):
        return {}
    first = parse_onionoo_ts(block["first"])
    interval = int(block.get("interval") or 0)
    factor = float(block.get("factor") or 1)
    out = {}
    for i, raw in enumerate(block["values"]):
        if raw is None:
            continue
        out[first + timedelta(seconds=i * interval)] = raw * factor
    return out


def pct(values, q):
    if not values:
        return None
    return float(np.percentile(values, q))


def summarize(values):
    if not values:
        return {"n": 0}
    arr = np.asarray(values, dtype=float)
    out = {
        "n": int(arr.size),
        "mean": float(arr.mean()),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }
    for q in PCTILES:
        out[f"p{q}"] = float(np.percentile(arr, q))
    return out


def coverage(values, lo, hi):
    if not values:
        return None
    arr = np.asarray(values, dtype=float)
    return float(np.mean((arr >= lo) & (arr <= hi)))


def relay_period_stats(write_block, read_block):
    w = history_map(write_block)
    r = history_map(read_block)
    if not w or not r:
        return None
    keys = sorted(set(w) & set(r))
    pairs = []
    for t in keys:
        wv, rv = w[t], r[t]
        if rv <= 0 or wv < 0:
            continue
        pairs.append((wv, rv, wv / rv))
    if not pairs:
        return None
    writes = [p[0] for p in pairs]
    reads = [p[1] for p in pairs]
    ratios = [p[2] for p in pairs]
    sum_w, sum_r = sum(writes), sum(reads)
    return {
        "n_points": len(pairs),
        "mean_write": float(np.mean(writes)),
        "mean_read": float(np.mean(reads)),
        "mean_thru": float(np.mean(writes) + np.mean(reads)) / 2.0,
        "ratio_of_means": (sum_w / sum_r) if sum_r else None,
        "mean_of_ratios": float(np.mean(ratios)),
        "median_of_ratios": float(np.median(ratios)),
        "p10_of_ratios": float(np.percentile(ratios, 10)),
        "p90_of_ratios": float(np.percentile(ratios, 90)),
        "daily_ratios": ratios,
    }


def style():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#cccccc",
        "axes.grid": True,
        "grid.color": "#eeeeee",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "savefig.bbox": "tight",
        "savefig.dpi": 140,
    })


def plot_period_box(by_period, title, ylabel, out_path):
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    data, labels = [], []
    for period in PERIODS:
        vals = by_period.get(period) or []
        if vals:
            data.append(vals)
            labels.append(f"{period}\nn={len(vals)}")
    if not data:
        plt.close(fig)
        return
    ax.boxplot(
        data, tick_labels=labels, showfliers=False, whis=(5, 95),
        medianprops={"color": NAVY, "linewidth": 1.8},
        boxprops={"color": BLUE},
        whiskerprops={"color": GRAY},
        capprops={"color": GRAY},
    )
    ax.axhspan(0.90, 1.15, color=GREEN, alpha=0.16, zorder=0)
    ax.axhline(1.0, color=GREEN, linestyle="--", linewidth=1.0)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(0.70, 1.50)
    fig.savefig(out_path)
    plt.close(fig)


def plot_role_box(by_role, title, out_path):
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    data, labels = [], []
    for role in ROLES:
        vals = by_role.get(role) or []
        if vals:
            data.append(vals)
            labels.append(f"{role}\nn={len(vals)}")
    if not data:
        plt.close(fig)
        return
    ax.boxplot(
        data, tick_labels=labels, showfliers=False, whis=(5, 95),
        medianprops={"color": NAVY, "linewidth": 1.8},
        boxprops={"color": BLUE},
        whiskerprops={"color": GRAY},
        capprops={"color": GRAY},
    )
    ax.axhspan(0.90, 1.15, color=GREEN, alpha=0.16, zorder=0)
    ax.axhline(1.0, color=GREEN, linestyle="--", linewidth=1.0)
    ax.set_ylabel("Write / read  (ratio of means)")
    ax.set_title(title)
    ax.set_ylim(0.70, 1.50)
    fig.savefig(out_path)
    plt.close(fig)


def plot_coverage_bars(coverage_rows, out_path):  # out_path last for save_both
    fig, ax = plt.subplots(figsize=(11.0, 5.8))
    x = np.arange(len(PERIODS))
    width = 0.16
    colors = [GRAY, ORANGE, GREEN, BLUE, BAD]
    for i, (lo, hi) in enumerate(CANDIDATE_BANDS):
        ys = [coverage_rows[period][f"{lo:.2f}-{hi:.2f}"] * 100 for period in PERIODS]
        ax.bar(x + (i - 2) * width, ys, width, color=colors[i],
               label=f"{lo:.2f}–{hi:.2f}")
    ax.set_xticks(x, [p.replace("_", " ") for p in PERIODS])
    ax.set_ylabel("Share of relays inside the band (%)")
    ax.set_title("Candidate write/read bands  ·  relays with mean throughput ≥ 50 KB/s")
    ax.set_ylim(0, 105)
    ax.legend(ncol=5, loc="lower center", fontsize=8)
    fig.savefig(out_path)
    plt.close(fig)


def plot_hist(values, title, out_path, lo=0.90, hi=1.15):
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    clipped = [v for v in values if 0.4 <= v <= 2.0]
    ax.hist(clipped, bins=80, color=BLUE, alpha=0.75, edgecolor="white")
    ax.axvspan(lo, hi, color=GREEN, alpha=0.18)
    ax.axvline(1.0, color=GREEN, linestyle="--", linewidth=1.2)
    ax.axvline(lo, color=GREEN, linewidth=1.2)
    ax.axvline(hi, color=GREEN, linewidth=1.2)
    ax.set_xlim(0.4, 2.0)
    ax.set_xlabel("Write / read")
    ax.set_ylabel("Relays")
    ax.set_title(title)
    fig.savefig(out_path)
    plt.close(fig)


def plot_hist_zones(values, out_path):
    """Typical vs uncommon vs investigate — 1.20 is in the amber shoulder."""
    fig, ax = plt.subplots(figsize=(10.8, 5.6))
    clipped = [v for v in values if 0.4 <= v <= 2.0]
    ax.hist(clipped, bins=80, color=BLUE, alpha=0.70, edgecolor="white")
    ax.axvspan(0.40, 0.80, color=BAD, alpha=0.12)
    ax.axvspan(0.80, 0.90, color=ORANGE, alpha=0.12)
    ax.axvspan(0.90, 1.15, color=GREEN, alpha=0.20)
    ax.axvspan(1.15, 1.50, color=ORANGE, alpha=0.12)
    ax.axvspan(1.50, 2.00, color=BAD, alpha=0.12)
    ax.axvline(1.0, color=GREEN, linestyle="--", linewidth=1.2)
    ax.axvline(1.20, color=NAVY, linestyle=":", linewidth=1.4)
    ax.annotate(
        "1.20  ·  uncommon, not investigate\n"
        "6.3% of 1M relays  ·  mostly Guards",
        xy=(1.20, 900), xytext=(1.42, 1600),
        fontsize=8.5, color=NAVY,
        arrowprops=dict(arrowstyle="->", color=NAVY),
        bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#dddddd"),
    )
    ax.set_xlim(0.4, 2.0)
    ax.set_xlabel("Write / read  (per-relay ratio of means)")
    ax.set_ylabel("Relays")
    ax.set_title("1-month write/read zones  ·  ≥50 KB/s   ·   green typical · amber uncommon · red investigate")
    fig.savefig(out_path)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bandwidth", default="/tmp/onionoo/bandwidth_all.json")
    parser.add_argument("--details", default="/tmp/onionoo/details.json")
    parser.add_argument("--data-out", default=str(
        Path(__file__).resolve().parent / "data" / "write_read_ratio_survey.json"))
    parser.add_argument("--plot-dir", default=str(
        Path(__file__).resolve().parent / "mockups"))
    parser.add_argument("--artifacts", default="/opt/cursor/artifacts")
    args = parser.parse_args()

    style()
    details = json.loads(Path(args.details).read_text())
    bw = json.loads(Path(args.bandwidth).read_text())
    det_pub = details.get("relays_published", "unknown")
    bw_pub = bw.get("relays_published", "unknown")
    det = {r["fingerprint"]: r for r in details.get("relays", [])}

    rows = []
    daily_by_period = defaultdict(list)
    for relay in bw.get("relays", []):
        fp = relay.get("fingerprint")
        info = det.get(fp) or {}
        role = role_of(info.get("flags"))
        write_h = relay.get("write_history") or {}
        read_h = relay.get("read_history") or {}
        for period in PERIODS:
            stats = relay_period_stats(write_h.get(period), read_h.get(period))
            if not stats:
                continue
            rec = {
                "fingerprint": fp,
                "nickname": info.get("nickname"),
                "role": role,
                "running": bool(info.get("running")),
                "period": period,
                "n_points": stats["n_points"],
                "mean_thru": stats["mean_thru"],
                "ratio_of_means": stats["ratio_of_means"],
                "mean_of_ratios": stats["mean_of_ratios"],
                "median_of_ratios": stats["median_of_ratios"],
                "p10_of_ratios": stats["p10_of_ratios"],
                "p90_of_ratios": stats["p90_of_ratios"],
            }
            rows.append(rec)
            daily_by_period[period].extend(stats["daily_ratios"])

    def select(period=None, role=None, min_thru=0, min_points=1, running_only=False):
        out = []
        for rec in rows:
            if period and rec["period"] != period:
                continue
            if role and rec["role"] != role:
                continue
            if rec["mean_thru"] < min_thru:
                continue
            if rec["n_points"] < min_points:
                continue
            if running_only and not rec["running"]:
                continue
            if rec["ratio_of_means"] is None or not math.isfinite(rec["ratio_of_means"]):
                continue
            out.append(rec)
        return out

    report = {
        "details_published": det_pub,
        "bandwidth_published": bw_pub,
        "details_n": len(det),
        "bandwidth_n": len(bw.get("relays", [])),
        "note": (
            "Per-relay ratio_of_means = sum(write)/sum(read) over aligned Onionoo "
            "buckets. Daily ratios are write_i/read_i. Tiny-traffic relays make "
            "noisy ratios; primary cuts use mean((write+read)/2) ≥ 50 KB/s."
        ),
        "periods": {},
    }

    coverage_50k = {}
    box_period = {}
    box_role_1m = defaultdict(list)

    for period in PERIODS:
        pdata = {"traffic_cuts": {}, "roles_50k": {}, "daily_50k_note": None}
        for cut in TRAFFIC_CUTS_BPS:
            recs = select(period=period, min_thru=cut, min_points=3)
            ratios = [r["ratio_of_means"] for r in recs]
            daily_means = [r["mean_of_ratios"] for r in recs]
            medians = [r["median_of_ratios"] for r in recs]
            entry = {
                "min_thru_bps": cut,
                "relays": summarize(ratios),
                "mean_of_daily_ratios": summarize(daily_means),
                "median_of_daily_ratios": summarize(medians),
                "band_coverage_ratio_of_means": {
                    f"{lo:.2f}-{hi:.2f}": coverage(ratios, lo, hi)
                    for lo, hi in CANDIDATE_BANDS
                },
            }
            pdata["traffic_cuts"][str(cut)] = entry
            if cut == 50_000:
                coverage_50k[period] = entry["band_coverage_ratio_of_means"]
                box_period[period] = ratios
                for role in ROLES:
                    role_recs = [r for r in recs if r["role"] == role]
                    role_ratios = [r["ratio_of_means"] for r in role_recs]
                    pdata["roles_50k"][role] = {
                        "relays": summarize(role_ratios),
                        "band_coverage_0.90-1.15": coverage(role_ratios, 0.90, 1.15),
                    }
                    if period == "1_month":
                        box_role_1m[role] = role_ratios

        # Daily-point distribution among 50 KB/s relays (chart strip is daily).
        daily_recs = select(period=period, min_thru=50_000, min_points=3)
        daily_pts = []
        for rec in daily_recs:
            # Recompute would be expensive; use stored p10/p90 span as a proxy
            # plus a second pass below for true daily points if needed.
            pass
        pdata["n_with_graph"] = len(select(period=period, min_thru=0, min_points=1))
        report["periods"][period] = pdata

    # True daily-point stats for ≥50 KB/s relays (1_month is the chart default).
    daily_report = {}
    for period in PERIODS:
        pts = []
        for relay in bw.get("relays", []):
            fp = relay.get("fingerprint")
            info = det.get(fp) or {}
            stats = relay_period_stats(
                (relay.get("write_history") or {}).get(period),
                (relay.get("read_history") or {}).get(period),
            )
            if not stats or stats["mean_thru"] < 50_000 or stats["n_points"] < 3:
                continue
            pts.extend(stats["daily_ratios"])
        daily_report[period] = {
            "points": summarize(pts),
            "band_coverage": {
                f"{lo:.2f}-{hi:.2f}": coverage(pts, lo, hi)
                for lo, hi in CANDIDATE_BANDS
            },
        }
    report["daily_points_50k"] = daily_report

    # How many 1_month relays sit outside 0.90–1.15, and how extreme?
    one_m = select(period="1_month", min_thru=50_000, min_points=3)
    outside = [r for r in one_m if r["ratio_of_means"] < 0.90 or r["ratio_of_means"] > 1.15]
    outside.sort(key=lambda r: abs(math.log(r["ratio_of_means"] or 1)), reverse=True)
    report["one_month_50k"] = {
        "n": len(one_m),
        "outside_0.90_1.15": len(outside),
        "outside_pct": (len(outside) / len(one_m)) if one_m else None,
        "below_0.90": sum(1 for r in one_m if r["ratio_of_means"] < 0.90),
        "above_1.15": sum(1 for r in one_m if r["ratio_of_means"] > 1.15),
        "below_0.80": sum(1 for r in one_m if r["ratio_of_means"] < 0.80),
        "above_1.25": sum(1 for r in one_m if r["ratio_of_means"] > 1.25),
        "worst_20": [
            {
                "nickname": r["nickname"],
                "fingerprint": r["fingerprint"],
                "role": r["role"],
                "ratio": round(r["ratio_of_means"], 3),
                "mean_thru_mbit": round(r["mean_thru"] * 8 / 1_000_000, 2),
            }
            for r in outside[:20]
        ],
    }

    # F3 family check if present in details.
    f3 = "3C89C80E2699FB6358BBB64FDC9547AFCB5C03F7"
    f3_det = det.get(f3) or {}
    family = set(f3_det.get("effective_family") or [])
    family.add(f3)
    fam_1m = [r for r in one_m if r["fingerprint"] in family]
    report["f3_family_1m_50k"] = {
        "n_in_sample": len(fam_1m),
        "ratios": sorted(
            [{"nickname": r["nickname"], "ratio": round(r["ratio_of_means"], 3),
              "role": r["role"]} for r in fam_1m],
            key=lambda x: x["ratio"], reverse=True,
        ),
    }

    data_path = Path(args.data_out)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(report, indent=2))
    print("wrote", data_path)

    plot_dir = Path(args.plot_dir)
    art = Path(args.artifacts)
    plot_dir.mkdir(parents=True, exist_ok=True)
    art.mkdir(parents=True, exist_ok=True)

    def save_both(name, fn, *fn_args):
        fn(*fn_args, plot_dir / name)
        try:
            fn(*fn_args, art / name)
        except OSError as exc:
            print("artifact write skipped:", name, exc)

    save_both(
        "ratio_survey_period_box.png",
        plot_period_box, box_period,
        "Write/read by Onionoo period  ·  mean throughput ≥ 50 KB/s",
        "Write / read  (ratio of means)",
    )
    save_both(
        "ratio_survey_role_box_1m.png",
        plot_role_box, box_role_1m,
        "1-month write/read by role  ·  mean throughput ≥ 50 KB/s",
    )
    save_both(
        "ratio_survey_band_coverage.png",
        plot_coverage_bars, coverage_50k,
    )
    save_both(
        "ratio_survey_hist_1m.png",
        plot_hist, box_period.get("1_month") or [],
        "1-month write/read  ·  all relays ≥ 50 KB/s  ·  green = 0.90–1.15 typical",
    )
    save_both(
        "ratio_survey_hist_zones.png",
        plot_hist_zones, box_period.get("1_month") or [],
    )

    # Console summary
    print(f"details {det_pub} n={len(det)}  bandwidth {bw_pub} n={len(bw.get('relays', []))}")
    for period in PERIODS:
        s = report["periods"][period]["traffic_cuts"]["50000"]["relays"]
        cov = report["periods"][period]["traffic_cuts"]["50000"]["band_coverage_ratio_of_means"]
        print(
            f"{period:10} n={s['n']:5}  p10={s['p10']:.3f}  p50={s['p50']:.3f}  "
            f"p90={s['p90']:.3f}  p95={s['p95']:.3f}  "
            f"in 0.90-1.15={cov['0.90-1.15']*100:.1f}%"
        )
    print("1M outside 0.90-1.15:", report["one_month_50k"]["outside_0.90_1.15"],
          f"({report['one_month_50k']['outside_pct']*100:.1f}%)")


if __name__ == "__main__":
    main()
