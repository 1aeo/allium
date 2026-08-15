#!/usr/bin/env python3
"""Generate top-10 operator chart mockups from a live Onionoo details snapshot.

Reads:
  /tmp/onionoo/details.json
  /tmp/onionoo/uptime_examples.json
  /tmp/onionoo/bandwidth_examples.json
  /tmp/onionoo/analysis.json  (optional; recomputed if missing)

Writes PNGs to --out (default: this directory's mockups/ plus /opt/cursor/artifacts).
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

BLUE = "#0072B2"
WRITE = "#6A3D9A"
VERM = "#D55E00"  # reserved for problem callouts, not series
GREEN = "#009E73"
SKY = "#56B4E9"
ORANGE = "#E69F00"
GRAY = "#666666"
NAVY = "#1B3A4B"

COUNTRY_NAMES = {
    "DE": "Germany", "NL": "Netherlands", "US": "United States", "FR": "France",
    "SE": "Sweden", "AT": "Austria", "CH": "Switzerland", "FI": "Finland",
    "GB": "United Kingdom", "CZ": "Czechia", "NO": "Norway", "LU": "Luxembourg",
    "IT": "Italy", "PL": "Poland", "ES": "Spain", "AU": "Australia",
    "JP": "Japan", "BR": "Brazil", "SG": "Singapore", "IN": "India",
    "HK": "Hong Kong", "CA": "Canada", "IS": "Iceland", "MD": "Moldova",
    "BG": "Bulgaria", "UA": "Ukraine", "DK": "Denmark", "HU": "Hungary",
}

GUARD_BW = 2_000_000


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


def footer(fig, published):
    fig.text(
        0.01, 0.01,
        f"Source: Onionoo details, relays_published {published} UTC  ·  Allium chart mockup",
        fontsize=8, color=GRAY,
    )


def role_of(flags):
    flags = flags or []
    exit_f = "Exit" in flags
    guard_f = "Guard" in flags
    if exit_f and guard_f:
        return "Guard+Exit"
    if exit_f:
        return "Exit"
    if guard_f:
        return "Guard"
    return "Middle"


def has_ipv6(or_addresses):
    for addr in or_addresses or []:
        if "[" in addr or (addr or "").count(":") > 1:
            return True
    return False


def parse_onionoo_ts(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def history_series(block):
    """Return (timestamps, values) from an Onionoo history object."""
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


def save(fig, paths):
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p)
    plt.close(fig)


def chart_cw_vs_bw(relays, published, out_paths):
    xs, ys, colors = [], [], []
    under_x, under_y = [], []
    ratios = []
    for r in relays:
        if not r.get("running"):
            continue
        obs = r.get("observed_bandwidth") or 0
        cw = r.get("consensus_weight") or 0
        if obs <= 0 or cw <= 0:
            continue
        mbit = obs * 8 / 1_000_000
        ratio = cw / obs
        ratios.append(ratio)
        xs.append(mbit)
        ys.append(cw)
        colors.append(BLUE)
    p10 = statistics.quantiles(ratios, n=10)[0] if len(ratios) >= 10 else 0
    # rebuild underutilized
    xs, ys, colors = [], [], []
    for r in relays:
        if not r.get("running"):
            continue
        obs = r.get("observed_bandwidth") or 0
        cw = r.get("consensus_weight") or 0
        if obs <= 0 or cw <= 0:
            continue
        mbit = obs * 8 / 1_000_000
        if (cw / obs) < p10 and obs >= 5_000_000:
            under_x.append(mbit)
            under_y.append(cw)
        else:
            xs.append(mbit)
            ys.append(cw)

    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.scatter(xs, ys, s=8, c=SKY, alpha=0.35, linewidths=0, label="Running relays")
    ax.scatter(under_x, under_y, s=14, c=VERM, alpha=0.7, linewidths=0,
               label=f"High capacity, low weight (bottom 10% CW/obs, n={len(under_x)})")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Observed bandwidth (Mbit/s)")
    ax.set_ylabel("Consensus weight")
    ax.set_title("1. Consensus weight vs observed bandwidth")
    ax.legend(loc="lower right")
    ax.annotate(
        "Operators ask: why is my weight so low\n"
        "for the bandwidth I offer?",
        xy=(0.02, 0.97), xycoords="axes fraction", va="top",
        fontsize=9, color=NAVY,
        bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#dddddd"),
    )
    footer(fig, published)
    save(fig, out_paths)


def chart_geo_bias(relays, published, out_paths):
    by_cc = defaultdict(list)
    for r in relays:
        if not r.get("running"):
            continue
        obs = r.get("observed_bandwidth") or 0
        cw = r.get("consensus_weight") or 0
        cc = (r.get("country") or "").upper()
        if obs > 0 and cw > 0 and cc:
            by_cc[cc].append(cw / obs)
    rows = []
    for cc, vals in by_cc.items():
        if len(vals) >= 30:
            rows.append((cc, statistics.median(vals), len(vals)))
    rows.sort(key=lambda x: x[1])
    # 8 lowest + 8 highest
    show = rows[:8] + rows[-8:]
    labels = [f"{COUNTRY_NAMES.get(cc, cc)} ({cc})  n={n}" for cc, _, n in show]
    vals = [v * 1e6 for _, v, _ in show]  # scale for readability
    colors = [VERM] * 8 + [GREEN] * 8

    fig, ax = plt.subplots(figsize=(11, 6.4))
    ax.barh(range(len(show)), vals, color=colors, height=0.72)
    ax.set_yticks(range(len(show)), labels)
    ax.set_xlabel("Median consensus weight per observed byte/s  (× 10⁻⁶)")
    ax.set_title("2. Geographic measurement bias (median CW / observed bandwidth)")
    de = next(v for cc, v, _ in rows if cc == "DE")
    au = next(v for cc, v, _ in rows if cc == "AU")
    ax.annotate(
        f"Germany median is {de/au:.1f}× Australia.\n"
        "Matches operator reports of low weight\n"
        "outside northern Europe.",
        xy=(0.98, 0.08), xycoords="axes fraction", ha="right", va="bottom",
        fontsize=9, color=NAVY,
        bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#dddddd"),
    )
    footer(fig, published)
    save(fig, out_paths)


def chart_guard_eligibility(relays, published, out_paths):
    running = [r for r in relays if r.get("running")]
    has_guard = sum(1 for r in running if "Guard" in (r.get("flags") or []))
    eligible_no = 0
    below = 0
    missing_stable = 0
    for r in running:
        flags = r.get("flags") or []
        if "Guard" in flags:
            continue
        obs = r.get("observed_bandwidth") or 0
        if obs >= GUARD_BW:
            eligible_no += 1
            if "Stable" not in flags:
                missing_stable += 1
        else:
            below += 1

    fig, ax = plt.subplots(figsize=(11, 6.0))
    labels = [
        "Has Guard flag",
        "≥ 2 MB/s observed,\nno Guard flag",
        "< 2 MB/s observed,\nno Guard flag",
    ]
    values = [has_guard, eligible_no, below]
    colors = [GREEN, ORANGE, GRAY]
    bars = ax.bar(labels, values, color=colors, width=0.62)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 80, f"{val:,}",
                ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_ylabel("Running relays")
    ax.set_title("3. Guard flag vs AuthDirGuardBWGuarantee (2 MB/s)")
    ax.set_ylim(0, max(values) * 1.18)
    ax.annotate(
        f"{missing_stable:,} of the {eligible_no:,} bandwidth-eligible\n"
        "relays also lack Stable — the usual\n"
        "reason Guard flaps after a restart.",
        xy=(0.98, 0.78), xycoords="axes fraction", ha="right", va="top",
        fontsize=9, color=NAVY,
        bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#dddddd"),
    )
    footer(fig, published)
    save(fig, out_paths)


def chart_overload(relays, published, out_paths):
    roles = ["Guard", "Guard+Exit", "Exit", "Middle"]
    totals = Counter()
    overloaded = Counter()
    for r in relays:
        rl = role_of(r.get("flags"))
        totals[rl] += 1
        if r.get("overload_general_timestamp"):
            overloaded[rl] += 1
    pcts = [100 * overloaded[r] / totals[r] for r in roles]
    counts = [overloaded[r] for r in roles]

    fig, ax = plt.subplots(figsize=(11, 6.0))
    bar_colors = [VERM if p >= 20 else ORANGE if p >= 10 else BLUE for p in pcts]
    bars = ax.bar(roles, pcts, color=bar_colors, width=0.62)
    for bar, pct, n, tot in zip(bars, pcts, counts, [totals[r] for r in roles]):
        ax.text(bar.get_x() + bar.get_width() / 2, pct + 0.4,
                f"{pct:.1f}%\n{n:,}/{tot:,}",
                ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Share of relays with overload_general set")
    ax.set_title("4. Overload prevalence by role")
    ax.set_ylim(0, max(pcts) * 1.28)
    ax.annotate(
        f"{sum(counts):,} relays currently report general overload.\n"
        "Forum/list: DNS timeouts, DoS circuit floods,\n"
        "and 'do not restart just because you are overloaded'.",
        xy=(0.02, 0.96), xycoords="axes fraction", va="top",
        fontsize=9, color=NAVY,
        bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#dddddd"),
    )
    footer(fig, published)
    save(fig, out_paths)


def chart_uptime(uptime_doc, published, out_paths):
    wanted = {
        "27A06581F1CE22D1BA4D160F6E7C7AABAC176242": ("th4r (high-weight Guard, DE)", BLUE),
        "3C89C80E2699FB6358BBB64FDC9547AFCB5C03F7": ("F3Netze (overloaded Exit, DE)", ORANGE),
    }
    fig, ax = plt.subplots(figsize=(11, 6.0))
    for relay in uptime_doc.get("relays", []):
        fp = relay.get("fingerprint")
        if fp not in wanted:
            continue
        label, color = wanted[fp]
        ts, vals = history_series((relay.get("uptime") or {}).get("1_month"))
        if not vals:
            continue
        # After applying Onionoo factor (~0.001), values are 0-1 fractions.
        if max(vals) <= 1.5:
            pct = [v * 100 for v in vals]
        elif max(vals) > 20:
            pct = [v / 9.99 for v in vals]
        else:
            pct = list(vals)
        ax.plot(ts, pct, color=color, linewidth=1.6, label=label)
    ax.set_ylim(40, 102)
    ax.set_ylabel("Running-flag uptime (%)")
    ax.set_title("5. One-month uptime — two live relays")
    ax.legend(loc="lower left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.annotate(
        "Losing Stable/Guard after a restart is the\n"
        "#2 operator thread topic. Chart the history\n"
        "already fetched from Onionoo /uptime.",
        xy=(0.98, 0.18), xycoords="axes fraction", ha="right", va="bottom",
        fontsize=9, color=NAVY,
        bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#dddddd"),
    )
    footer(fig, published)
    save(fig, out_paths)


def chart_bandwidth_history(bw_doc, details_relays, published, out_paths):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    fig, (ax, axr) = plt.subplots(
        2, 1, figsize=(11, 7.0), sharex=True,
        gridspec_kw={"height_ratios": [3.1, 1.3], "hspace": 0.08},
    )
    fp = "3C89C80E2699FB6358BBB64FDC9547AFCB5C03F7"
    relay = next((r for r in bw_doc.get("relays", []) if r.get("fingerprint") == fp), None)
    det = next((r for r in details_relays if r.get("fingerprint") == fp), {})
    if relay:
        w_ts, w_vals = history_series((relay.get("write_history") or {}).get("1_month"))
        _, r_vals = history_series((relay.get("read_history") or {}).get("1_month"))
        w_mbit = [v * 8 / 1_000_000 for v in w_vals]
        r_mbit = [v * 8 / 1_000_000 for v in r_vals]
        advertised = (det.get("advertised_bandwidth") or 0) * 8 / 1_000_000
        ax.plot(w_ts, w_mbit, color=WRITE, linewidth=1.8, label="Write (outbound)")
        ax.plot(w_ts, r_mbit, color=BLUE, linewidth=1.8, label="Read (inbound)")
        if advertised:
            ax.axhline(advertised, color=ORANGE, linestyle="--", linewidth=1.4,
                       label=f"Advertised  {advertised:.0f} Mbit/s")
            ax.set_ylim(0, max(advertised, max(w_mbit + r_mbit)) * 1.08)
        events = []
        if det.get("last_restarted"):
            when = parse_onionoo_ts(det["last_restarted"])
            events.append({
                "kind": "restart",
                "when": when,
                "color": NAVY,
                "ls": "-.",
                "legend": f"Last restarted  {when.strftime('%-d %b')}",
            })
        ov = det.get("overload_general_timestamp")
        if ov:
            when = datetime.fromtimestamp(ov / 1000.0, tz=timezone.utc)
            ov_end = when + timedelta(hours=72)
            events.append({
                "kind": "overload",
                "when": when,
                "end": ov_end,
                "color": "#C0392B",
                "legend": (
                    f"Overload flag (72h)  {when.strftime('%-d %b %H:%M')} → "
                    f"{ov_end.strftime('%-d %b %H:%M')} UTC"
                ),
            })
        xmax = w_ts[-1] if w_ts else None
        for ev in events:
            if ev["kind"] == "overload":
                ax.axvspan(ev["when"], ev["end"], color=ev["color"], alpha=0.14, zorder=0)
                axr.axvspan(ev["when"], ev["end"], color=ev["color"], alpha=0.14, zorder=0)
                ax.axvline(ev["when"], color=ev["color"], linestyle=":", linewidth=1.2)
                axr.axvline(ev["when"], color=ev["color"], linestyle=":", linewidth=1.2)
                if xmax is None or ev["end"] > xmax:
                    xmax = ev["end"]
            else:
                ax.axvline(ev["when"], color=ev["color"], linestyle=ev["ls"], linewidth=1.8)
                axr.axvline(ev["when"], color=ev["color"], linestyle=ev["ls"], linewidth=1.8)
        if w_ts and xmax:
            pad = (xmax - w_ts[0]) * 0.03
            ax.set_xlim(w_ts[0], xmax + pad)
        handles = [
            Line2D([0], [0], color=WRITE, lw=1.8, label="Write (outbound)"),
            Line2D([0], [0], color=BLUE, lw=1.8, label="Read (inbound)"),
            Line2D([0], [0], color=ORANGE, ls="--", lw=1.4,
                   label=f"Advertised  {advertised:.0f} Mbit/s"),
        ]
        for ev in events:
            if ev["kind"] == "overload":
                handles.append(Patch(
                    facecolor=ev["color"], alpha=0.22, edgecolor=ev["color"],
                    label=ev["legend"],
                ))
            else:
                handles.append(Line2D(
                    [0], [0], color=ev["color"], linestyle=ev["ls"], lw=1.8,
                    label=ev["legend"],
                ))
        ax.legend(handles=handles, loc="upper left", fontsize=9, ncol=2)

        ratio = [w / r if r else float("nan") for w, r in zip(w_mbit, r_mbit)]
        axr.axhspan(0.90, 1.15, color=GREEN, alpha=0.16)
        axr.axhspan(0.50, 0.90, color=VERM, alpha=0.07)
        axr.axhspan(1.15, 1.70, color=VERM, alpha=0.07)
        axr.axhline(1.0, color=GREEN, linestyle="--", linewidth=1.0)
        axr.plot(w_ts, ratio, color=NAVY, linewidth=1.6)
        axr.set_ylim(0.50, 1.70)
        axr.set_ylabel("Write / read")
        axr.legend(handles=[
            Patch(facecolor=GREEN, alpha=0.22, edgecolor=GREEN,
                  label="Expected  0.90–1.15  (fixed, not a percentile)"),
            Line2D([0], [0], color=NAVY, lw=1.6, label="This relay  write / read"),
            Patch(facecolor=VERM, alpha=0.16, edgecolor=VERM,
                  label="Outside the band — unusual, usually something wrong"),
        ], loc="upper right", fontsize=8, frameon=True, edgecolor="#dddddd")
        axr.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.set_ylabel("Throughput (Mbit/s)")
    ax.set_title("6. Bandwidth history — F3Netze (overloaded exit)")
    footer(fig, published)
    save(fig, out_paths)


def chart_country_cw(relays, published, out_paths):
    cw = Counter()
    n = Counter()
    for r in relays:
        cc = (r.get("country") or "??").upper()
        cw[cc] += r.get("consensus_weight") or 0
        n[cc] += 1
    total = sum(cw.values()) or 1
    top = cw.most_common(12)
    labels = [f"{COUNTRY_NAMES.get(cc, cc)} ({cc})" for cc, _ in top]
    pcts = [100 * v / total for _, v in top]
    fig, ax = plt.subplots(figsize=(11, 6.2))
    bars = ax.barh(range(len(top))[::-1], pcts[::-1], color=BLUE, height=0.72)
    ax.set_yticks(range(len(top))[::-1], labels[::-1])
    ax.set_xlabel("Share of network consensus weight (%)")
    ax.set_title("7. Consensus-weight concentration by country")
    cum3 = sum(v for _, v in top[:3]) / total * 100
    for bar, pct, (cc, _) in zip(bars, pcts[::-1], top[::-1]):
        ax.text(pct + 0.2, bar.get_y() + bar.get_height() / 2,
                f"{pct:.1f}%  ·  {n[cc]:,} relays", va="center", fontsize=8, color=GRAY)
    ax.set_xlim(0, max(pcts) * 1.35)
    ax.annotate(
        f"DE + NL + US hold {cum3:.0f}% of consensus weight.\n"
        "Forum: 'Why don't we encourage relays in East Asia?'",
        xy=(0.98, 0.18), xycoords="axes fraction", ha="right",
        fontsize=9, color=NAVY,
        bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#dddddd"),
    )
    footer(fig, published)
    save(fig, out_paths)


def chart_as_cw(relays, published, out_paths):
    cw = Counter()
    n = Counter()
    names = {}
    for r in relays:
        asn = r.get("as") or "AS?"
        cw[asn] += r.get("consensus_weight") or 0
        n[asn] += 1
        names[asn] = r.get("as_name") or asn
    total = sum(cw.values()) or 1
    top = cw.most_common(12)
    labels = []
    for asn, _ in top:
        name = names[asn]
        if len(name) > 32:
            name = name[:30] + "…"
        labels.append(f"{name}  {asn}")
    pcts = [100 * v / total for _, v in top]
    fig, ax = plt.subplots(figsize=(11, 6.6))
    bars = ax.barh(range(len(top))[::-1], pcts[::-1], color=BLUE, height=0.72)
    ax.set_yticks(range(len(top))[::-1], labels[::-1])
    ax.set_xlabel("Share of network consensus weight (%)")
    ax.set_title("8. Consensus-weight concentration by Autonomous System")
    cum3 = sum(v for _, v in top[:3]) / total * 100
    for bar, pct, (asn, _) in zip(bars, pcts[::-1], top[::-1]):
        ax.text(pct + 0.15, bar.get_y() + bar.get_height() / 2,
                f"{pct:.1f}%  ·  {n[asn]:,} relays", va="center", fontsize=8, color=GRAY)
    ax.set_xlim(0, max(pcts) * 1.38)
    ax.annotate(
        f"Top 3 ASes hold {cum3:.0f}% of consensus weight.\n"
        "Operators ask which providers to use — and\n"
        "whether their AS is already too big.",
        xy=(0.98, 0.08), xycoords="axes fraction", ha="right", va="bottom",
        fontsize=9, color=NAVY,
        bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#dddddd"),
    )
    footer(fig, published)
    save(fig, out_paths)


def chart_ipv6(relays, published, out_paths):
    roles = ["Exit", "Guard+Exit", "Guard", "Middle"]
    have = Counter()
    tot = Counter()
    for r in relays:
        rl = role_of(r.get("flags"))
        tot[rl] += 1
        if has_ipv6(r.get("or_addresses")):
            have[rl] += 1
    pcts = [100 * have[r] / tot[r] for r in roles]
    fig, ax = plt.subplots(figsize=(11, 6.0))
    bars = ax.bar(roles, pcts, color=[BLUE, SKY, ORANGE, GRAY], width=0.62)
    for bar, pct, r in zip(bars, pcts, roles):
        ax.text(bar.get_x() + bar.get_width() / 2, pct + 1.2,
                f"{pct:.0f}%\n{have[r]:,}/{tot[r]:,}",
                ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Share advertising an IPv6 OR address")
    ax.set_ylim(0, 100)
    ax.set_title("9. IPv6 advertisement by role")
    ax.annotate(
        "Broken advertised IPv6 is a recurring cause of\n"
        "'not in consensus' / lost flags. Advertise it\n"
        "only if directory authorities can reach it.",
        xy=(0.02, 0.96), xycoords="axes fraction", va="top",
        fontsize=9, color=NAVY,
        bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#dddddd"),
    )
    footer(fig, published)
    save(fig, out_paths)


def chart_role_mix(relays, published, out_paths):
    roles = ["Guard", "Guard+Exit", "Exit", "Middle"]
    counts = Counter()
    cw = Counter()
    for r in relays:
        rl = role_of(r.get("flags"))
        counts[rl] += 1
        cw[rl] += r.get("consensus_weight") or 0
    n_tot = sum(counts.values()) or 1
    cw_tot = sum(cw.values()) or 1
    x = np.arange(len(roles))
    w = 0.36
    fig, ax = plt.subplots(figsize=(11, 6.0))
    b1 = ax.bar(x - w / 2, [100 * counts[r] / n_tot for r in roles], w,
                color=SKY, label="Share of relays")
    b2 = ax.bar(x + w / 2, [100 * cw[r] / cw_tot for r in roles], w,
                color=BLUE, label="Share of consensus weight")
    ax.set_xticks(x, roles)
    ax.set_ylabel("Percent of network")
    ax.set_title("10. Role mix — relay count vs consensus weight")
    ax.legend(loc="upper right")
    ax.set_ylim(0, 65)
    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
                    f"{bar.get_height():.0f}%", ha="center", fontsize=8)
    ax.annotate(
        "Middles are common but carry little weight.\n"
        "Operators asking 'exit or guard?' need this\n"
        "before they pick a role.",
        xy=(0.02, 0.96), xycoords="axes fraction", va="top",
        fontsize=9, color=NAVY,
        bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#dddddd"),
    )
    footer(fig, published)
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
    relays = details.get("relays", [])
    published = details.get("relays_published", "unknown")
    uptime_doc = json.loads(Path(args.uptime).read_text())
    bw_doc = json.loads(Path(args.bandwidth).read_text())

    out = Path(args.out)
    art = Path(args.artifacts)
    jobs = [
        ("chart_01_cw_vs_bandwidth.png", chart_cw_vs_bw, (relays, published)),
        ("chart_02_geo_measurement_bias.png", chart_geo_bias, (relays, published)),
        ("chart_03_guard_eligibility.png", chart_guard_eligibility, (relays, published)),
        ("chart_04_overload_by_role.png", chart_overload, (relays, published)),
        ("chart_05_uptime_history.png", chart_uptime, (uptime_doc, published)),
        ("chart_06_bandwidth_history.png", chart_bandwidth_history, (bw_doc, relays, published)),
        ("chart_07_country_cw.png", chart_country_cw, (relays, published)),
        ("chart_08_as_cw.png", chart_as_cw, (relays, published)),
        ("chart_09_ipv6_by_role.png", chart_ipv6, (relays, published)),
        ("chart_10_role_mix.png", chart_role_mix, (relays, published)),
    ]
    for name, fn, fn_args in jobs:
        paths = [out / name, art / name]
        fn(*fn_args, paths)
        print("wrote", name)


if __name__ == "__main__":
    main()
