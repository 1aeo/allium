"""Slim style-5 / option C renderer for ``relay_bandwidth_1m``.

Extracted from the locked mockup look. Does not import matplotlib at
module load — workers call ``_ensure_mpl()`` after ``matplotlib.use("Agg")``.
"""

from datetime import datetime, timezone

from ..stability_utils import current_overload_status
from .bands import (
    RATIO_INVESTIGATE_HI,
    RATIO_LEGEND_SHELF,
    RATIO_SCALE_LO,
    band_legend_labels,
    bands_for_flags,
    census_footnote,
    ratio_strip_data_hi,
)
from .identity import chart_identity
from .outcome import (
    SHIPPED_OUTCOME_STYLE,
    format_day,
    format_outcome_subtitle,
    summarize_bandwidth_outcome,
)
from .series import (
    advertised_mbit,
    aligned_1m_series,
    overlay_lookup,
    parse_onionoo_ts,
)

# Okabe–Ito. Red is reserved for problems.
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
AMBER = ORANGE

IDENTITY_FONTSIZE = 13
IDENTITY_TITLE_GAP_PT = 12
IDENTITY_EXTRA_FIG_H = 0.48
IDENTITY_TOP_SHIFT = 0.075
IDENTITY_TITLE_PAD_BOOST = 6
THROUGHPUT_TITLE_PAD = 10
SUBTITLE_TITLE_PAD = 22
RATIO_TITLE_PAD = THROUGHPUT_TITLE_PAD
LEGEND_FONTSIZE = 8.0

CHROME = {
    "spines": "left_bottom",
    "grid": "y",
    "title_loc": "left",
    "weights": "hierarchy",
    "subtitle": True,
    "callout": True,
}
CHROME_WEIGHTS = {
    "write": 2.35,
    "read": 1.65,
    "advertised": 1.15,
    "restart": 1.25,
    "relay": 2.15,
    "family": 1.25,
    "peers": 1.25,
    "investigate": 2.3,
}

_plt = None
_np = None
_mdates = None
_Line2D = None
_Patch = None
_ScaledTranslation = None


def _ensure_mpl():
    """Import pyplot once per process. Caller must have set Agg."""
    global _plt, _np, _mdates, _Line2D, _Patch, _ScaledTranslation
    if _plt is not None:
        return _plt
    import matplotlib

    if matplotlib.get_backend().lower() != "agg":
        matplotlib.use("Agg", force=True)
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.transforms import ScaledTranslation

    _plt = plt
    _np = np
    _mdates = mdates
    _Line2D = Line2D
    _Patch = Patch
    _ScaledTranslation = ScaledTranslation
    return _plt


def _apply_style(plt):
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
        "savefig.dpi": 140,
    })


def _trim_rgba(rgba, pad_px=12, white=250):
    """Crop outer white. Do not use savefig(bbox='tight') for this figure."""
    rgb = rgba[:, :, :3]
    ink = rgb.min(axis=2) < white
    rows = _np.where(ink.any(axis=1))[0]
    cols = _np.where(ink.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return rgba
    y0 = max(0, int(rows[0]) - pad_px)
    y1 = min(rgb.shape[0], int(rows[-1]) + pad_px + 1)
    x0 = max(0, int(cols[0]) - pad_px)
    x1 = min(rgb.shape[1], int(cols[-1]) + pad_px + 1)
    return rgba[y0:y1, x0:x1]


def _save_trimmed(fig, dest_path):
    import os

    fig.canvas.draw()
    rgba = _np.asarray(fig.canvas.buffer_rgba())
    parent = os.path.dirname(dest_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = dest_path + ".tmp"
    _plt.imsave(tmp, _trim_rgba(rgba))
    os.replace(tmp, dest_path)
    _plt.close(fig)


def _with_role(title, bands):
    role = (bands or {}).get("role") or ""
    if not title or not role or role in title:
        return title
    return "{}  ·  {}".format(title, role)


def _sibling_ratio_title(throughput_title, bands):
    if not throughput_title:
        return _with_role("Write / read", bands)
    metric = throughput_title.split("\n")[-1]
    idx = metric.find("Throughput")
    if idx >= 0:
        return "Write / read" + metric[idx + len("Throughput"):]
    return _with_role("Write / read", bands)


def overload_now_status(relay, published):
    if isinstance(published, str):
        try:
            now_ts = parse_onionoo_ts(published).timestamp()
        except (TypeError, ValueError, AttributeError):
            now_ts = None
    elif isinstance(published, datetime):
        now_ts = published.timestamp()
    else:
        now_ts = published
    return current_overload_status(relay, now_ts)


def _overload_quiet_text(status):
    if not status:
        return None
    last = status.get("last_report")
    if last:
        when = "{} {} UTC".format(
            format_day(last), last.strftime("%H:%M"),
        )
        return "currently overloaded · last report {}".format(when)
    return "currently overloaded"


def _event_whens(ev):
    if ev.get("whens"):
        return list(ev["whens"])
    if ev.get("when") is not None:
        return [ev["when"]]
    return []


def _restart_legend_label(whens):
    dates = ", ".join(
        format_day(w) for w in sorted(set(whens), reverse=True)
    )
    return "Last restarted  {}".format(dates) if dates else "Last restarted"


def restart_events(last_restarted):
    when = parse_onionoo_ts(last_restarted)
    if when is None:
        return []
    return [{
        "kind": "restart",
        "when": when,
        "whens": [when],
        "color": RESTART,
        "ls": "-.",
        "legend": _restart_legend_label([when]),
    }]


def _events_in_span(events, ts):
    if not ts:
        return []
    lo, hi = ts[0], ts[-1]
    out = []
    for ev in events or []:
        if ev.get("kind") == "overload":
            continue
        whens = [w for w in _event_whens(ev) if lo <= w <= hi]
        if not whens:
            continue
        clipped = dict(ev)
        clipped["whens"] = whens
        clipped["when"] = whens[0]
        if ev.get("kind") == "restart":
            clipped["legend"] = _restart_legend_label(whens)
        out.append(clipped)
    return out


def _draw_event_lines(ax, events, lw=1.8):
    for ev in events or []:
        if ev.get("kind") == "overload":
            continue
        for when in _event_whens(ev):
            ax.axvline(
                when, color=ev.get("color", RESTART),
                linestyle=ev.get("ls", "-."), linewidth=lw,
                alpha=0.95, zorder=3,
            )


def _event_legend_handles(events):
    handles = []
    restart_whens = []
    restart_style = None
    for ev in events or []:
        if ev.get("kind") == "overload":
            continue
        if ev.get("kind") == "restart":
            restart_whens.extend(_event_whens(ev))
            restart_style = ev
            continue
        handles.append(_Line2D(
            [0], [0], color=ev["color"], linestyle=ev["ls"], linewidth=1.8,
            label=ev["legend"],
        ))
    if restart_whens and restart_style:
        handles.append(_Line2D(
            [0], [0], color=restart_style["color"],
            linestyle=restart_style["ls"], linewidth=1.8,
            label=_restart_legend_label(restart_whens),
        ))
    return handles


def _throughput_legend_handles(advertised, events, overload_status, in_legend):
    handles = [
        _Line2D([0], [0], color=WRITE, linewidth=1.8, label="Write (outbound)"),
        _Line2D([0], [0], color=BLUE, linewidth=1.8, label="Read (inbound)"),
    ]
    if advertised:
        handles.append(_Line2D(
            [0], [0], color=ORANGE, linestyle="--", linewidth=1.4,
            label="Advertised  {:.0f} Mbit/s".format(advertised),
        ))
    handles.extend(_event_legend_handles(events))
    if in_legend and overload_status:
        handles.append(_Line2D(
            [0], [0], color=OVERLOAD, marker="D", linestyle="None",
            markersize=6, label=_overload_quiet_text(overload_status),
        ))
    return handles


def _legend_style():
    return dict(
        fontsize=LEGEND_FONTSIZE,
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


def _place_legend_above(ax, handles, wrap_last=False):
    if not handles:
        return
    style = _legend_style()
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
    ax.legend(handles=handles, loc="upper left", ncol=min(len(handles), 4), **style)


def _ratio_legend_style():
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


def _row_major_ratio_handles(series, bands):
    n = max(len(series), len(bands), 1)
    out = []
    for i in range(n):
        if i < len(series):
            out.append(series[i])
        if i < len(bands):
            out.append(bands[i])
    return out


def _place_ratio_legend_shelf(ax, handles):
    if not handles:
        return None
    series = [h for h in handles if not isinstance(h, _Patch)]
    bands = [h for h in handles if isinstance(h, _Patch)]
    return ax.legend(
        handles=_row_major_ratio_handles(series, bands),
        loc="upper left",
        ncol=max(len(series), 1),
        **_ratio_legend_style(),
    )


def _apply_chrome_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#bbbbbb")
    ax.spines["bottom"].set_color("#bbbbbb")
    ax.grid(True, axis="y")
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#555555")


def _apply_method_subtitle(ax, text):
    if not text:
        return
    ax.text(
        0.0, 1.028, text, transform=ax.transAxes, ha="left", va="bottom",
        fontsize=8.0, color="#6B7280",
    )


def _apply_chart_identity(ax, identity, loc="left", title_pad=None):
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
        transform=ax.transAxes + _ScaledTranslation(
            0, offset_in, fig.dpi_scale_trans,
        ),
        ha=ha, va="bottom",
        fontsize=IDENTITY_FONTSIZE, fontweight="bold", color=NAVY,
        clip_on=False,
    )


def _pad_xlim(ax, ts):
    if not ts:
        return
    xmin, xmax = ts[0], ts[-1]
    pad = (xmax - xmin) * 0.03
    ax.set_xlim(xmin, xmax + pad)


def _date_axis(ax):
    ax.xaxis.set_major_formatter(_mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(_mdates.WeekdayLocator(interval=1))


def _throughput_ylim(ax, read_m, write_m, advertised, legend_rows=1):
    data_max = max(list(write_m) + list(read_m) + [0.0])
    ceiling = max(advertised or 0.0, data_max) or 1.0
    extra = 1.28 if legend_rows >= 2 else 1.26
    ax.set_ylim(0, ceiling * extra)


def _apply_throughput_title(ax, title, overload_status, overload_mode, loc, pad):
    if not title:
        return
    if loc == "left":
        ax.set_title(title, loc="left", pad=pad)
        if overload_mode == "title" and overload_status:
            ax.set_title(
                _overload_quiet_text(overload_status),
                loc="right", pad=pad, color=OVERLOAD,
                fontsize=9, fontweight="normal",
            )
        return
    ax.set_title(title, pad=pad)


def _ratio_legend_handles(overlays, bands):
    overlays = overlays or {}
    copy = band_legend_labels(bands)
    op_n = overlays.get("family_n") or 0
    handles = [
        _Line2D([0], [0], color=NAVY, linewidth=1.6, label="This relay"),
    ]
    if overlays.get("operator"):
        handles.append(_Line2D(
            [0], [0], color=GRAY, linestyle=":", linewidth=1.6,
            label=overlays.get("operator_label")
            or "Operator Family (median, n={})".format(op_n),
        ))
    if overlays.get("role"):
        handles.append(_Line2D(
            [0], [0], color=SKY, linestyle="--", linewidth=1.4,
            label=overlays.get("role_label") or "Peers (network median)",
        ))
    handles.extend([
        _Patch(facecolor=GREEN, alpha=0.22, edgecolor=GREEN, label=copy["typical"]),
        _Patch(facecolor=AMBER, alpha=0.16, edgecolor=AMBER, label=copy["uncommon"]),
        _Patch(facecolor=BAD, alpha=0.16, edgecolor=BAD, label=copy["investigate"]),
    ])
    return handles


def _apply_ratio_yticks(axr, bands, ylo, yhi):
    tlo, thi = bands["typical_lo"], bands["typical_hi"]
    ihi = bands["invest_hi"]
    typical_mid = (tlo + thi) / 2.0
    ticks = [ylo, 1.0, 1.5]
    labels = ["{:.1f}".format(ylo), "1.0", "1.5"]
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


def _auto_spike_callout(ax, ts, write_m, read_m, bands):
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
    from datetime import timedelta
    by_day = {row[1].date(): row for row in rows}
    run = [peak]
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
        label = "{} · write/read {:.2f} · {}".format(
            format_day(peak_t), peak[0], scale_bit,
        )
    else:
        ratios = " / ".join("{:.2f}".format(row[0]) for row in run)
        label = "{}–{} · write/read {} · {}".format(
            run[0][1].day, format_day(run[-1][1]), ratios, scale_bit,
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


def _plot_ratio_strip(axr, ts, read_m, write_m, events, overlays, bands):
    overlays = overlays or {}
    tlo, thi = bands["typical_lo"], bands["typical_hi"]
    ilo, ihi = bands["invest_lo"], bands["invest_hi"]
    ratio = _np.array([
        (w / r) if r else _np.nan for w, r in zip(write_m, read_m)
    ])
    ylo = RATIO_SCALE_LO
    yhi = ratio_strip_data_hi(ihi, ilo)
    shelf = RATIO_LEGEND_SHELF
    axr.axhspan(0.45, ilo, color=BAD, alpha=0.10, zorder=0)
    axr.axhspan(ilo, tlo, color=AMBER, alpha=0.10, zorder=0)
    axr.axhspan(tlo, thi, color=GREEN, alpha=0.16, zorder=0)
    axr.axhspan(thi, ihi, color=AMBER, alpha=0.10, zorder=0)
    # Always-on top Investigate: invest_hi → data top is a real red shelf.
    axr.axhspan(ihi, yhi, color=BAD, alpha=0.10, zorder=0)
    axr.axhspan(yhi, yhi + shelf + 0.02, color="white", zorder=0)
    axr.axhline(1.0, color=GREEN, linestyle="--", linewidth=1.0, zorder=1)
    role_vals = overlays.get("role_values")
    if role_vals is not None:
        axr.plot(
            ts, [_np.nan if v is None else v for v in role_vals],
            color=SKY, linestyle="--", linewidth=CHROME_WEIGHTS["peers"],
            zorder=2,
        )
    op_vals = overlays.get("operator_values")
    if op_vals is not None:
        axr.plot(
            ts, [_np.nan if v is None else v for v in op_vals],
            color=GRAY, linestyle=":", linewidth=CHROME_WEIGHTS["family"],
            zorder=2,
        )
    y_plot = _np.clip(ratio, ylo, yhi)
    investigate = (ratio < ilo) | (ratio > ihi)
    axr.plot(ts, y_plot, color=NAVY, linewidth=CHROME_WEIGHTS["relay"], zorder=3)
    if investigate.any():
        axr.plot(
            ts, _np.ma.masked_where(~investigate, y_plot),
            color=BAD, linewidth=CHROME_WEIGHTS["investigate"], zorder=4,
        )
    off_hi = _np.isfinite(ratio) & (ratio > yhi)
    off_lo = _np.isfinite(ratio) & (ratio < ylo)
    ts_arr = _np.array(ts)
    if off_hi.any():
        axr.scatter(
            ts_arr[off_hi], _np.full(int(off_hi.sum()), yhi),
            marker="^", color=BAD, s=32, zorder=5, clip_on=False,
        )
    if off_lo.any():
        axr.scatter(
            ts_arr[off_lo], _np.full(int(off_lo.sum()), ylo),
            marker="v", color=BAD, s=32, zorder=5, clip_on=False,
        )
    _draw_event_lines(axr, events, lw=CHROME_WEIGHTS["restart"])
    _apply_chrome_axes(axr)
    _pad_xlim(axr, ts)
    axr.set_ylabel("Write / read")
    axr.set_ylim(ylo, yhi + shelf)
    _apply_ratio_yticks(axr, bands, ylo, yhi)
    _date_axis(axr)
    handles = _ratio_legend_handles(overlays, bands)
    _place_ratio_legend_shelf(axr, handles)


def _draw_throughput(ax, ts, read_m, write_m, advertised, events, legend_rows):
    ev = _events_in_span(events, ts)
    ax.plot(ts, write_m, color=WRITE, linewidth=CHROME_WEIGHTS["write"])
    ax.plot(ts, read_m, color=BLUE, linewidth=CHROME_WEIGHTS["read"])
    if advertised:
        ax.axhline(
            advertised, color=ORANGE, linestyle="--",
            linewidth=CHROME_WEIGHTS["advertised"],
        )
    _draw_event_lines(ax, ev, lw=CHROME_WEIGHTS["restart"])
    _apply_chrome_axes(ax)
    _pad_xlim(ax, ts)
    _throughput_ylim(ax, read_m, write_m, advertised, legend_rows=legend_rows)
    ax.set_ylabel("Throughput (Mbit/s)")
    _date_axis(ax)


def _relay_for_overload(job):
    return {
        "overload_general_timestamp": job.get("overload_general_timestamp"),
        "overload_ratelimits": job.get("overload_ratelimits"),
        "overload_fd_exhausted": job.get("overload_fd_exhausted"),
    }


def _plot_overlays(job, ts, write_1m):
    family = job.get("family_overlay")
    role = job.get("role_overlay")
    overlays = {
        "family_n": (family or {}).get("n") or 0,
        "operator_label": None,
        "role_label": "Peers (network median)",
        "operator": {},
        "role": {},
        "operator_values": None,
        "role_values": None,
    }
    if family and family.get("n", 0) >= 2:
        values = overlay_lookup(ts, family, write_1m)
        if values is not None:
            overlays["operator_values"] = values
            overlays["operator"] = {
                t: v for t, v in zip(ts, values) if v is not None
            }
            overlays["operator_label"] = (
                "Operator Family (median, n={})".format(family["n"])
            )
    if role:
        values = overlay_lookup(ts, role, write_1m)
        if values is not None:
            overlays["role_values"] = values
            overlays["role"] = {
                t: v for t, v in zip(ts, values) if v is not None
            }
    return overlays


def render_relay_bandwidth_1m(job, dest_path):
    """Draw the locked dual-line + write/read figure and write ``dest_path``.

    ``job`` is a slim picklable dict (details fields + raw 1M history +
    aligned overlays). Returns ``dest_path``. Raises ``ValueError`` when
    history is too thin to draw.
    """
    plt = _ensure_mpl()
    _apply_style(plt)

    write_1m = job.get("write_1m")
    read_1m = job.get("read_1m")
    series = aligned_1m_series(write_1m, read_1m)
    if not series:
        raise ValueError("thin or missing 1M write/read history")

    ts = series["ts"]
    write_m = series["write_m"]
    read_m = series["read_m"]
    adv = advertised_mbit(job.get("advertised_bandwidth"))
    events = restart_events(job.get("last_restarted"))
    bands = job.get("bands") or bands_for_flags(job.get("flags"))
    overlays = _plot_overlays(job, ts, write_1m)
    overlays["bands"] = bands
    overload_status = overload_now_status(
        _relay_for_overload(job), job.get("relays_published"),
    )
    overload_mode = "legend" if overload_status else "title"
    wrap_last = bool(overload_status)
    outcome = summarize_bandwidth_outcome(
        ts, write_m, read_m, adv, events, overlays, bands, overload_status,
    )
    thru_sub = format_outcome_subtitle(
        outcome, "throughput", SHIPPED_OUTCOME_STYLE,
    )
    ratio_sub = format_outcome_subtitle(outcome, "ratio", SHIPPED_OUTCOME_STYLE)
    subtitle_on = bool(thru_sub or ratio_sub)

    nickname = job.get("nickname") or ""
    operator = job.get("operator") or ""
    ident = chart_identity(nickname, operator)
    identity_on = bool(ident)

    hspace = 0.34 if subtitle_on else 0.24
    fig_h = 7.6 if subtitle_on else 7.4
    top = 0.86 if subtitle_on else 0.91
    if identity_on:
        fig_h += IDENTITY_EXTRA_FIG_H
        top = max(0.70, top - IDENTITY_TOP_SHIFT)
    fig, (ax, axr) = plt.subplots(
        2, 1, figsize=(10.8, fig_h), sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1.75], "hspace": hspace},
    )
    fig.subplots_adjust(top=top, bottom=0.16)
    plt.setp(ax.get_xticklabels(), visible=False)

    _draw_throughput(
        ax, ts, read_m, write_m, adv, events,
        legend_rows=2 if wrap_last else 1,
    )
    title = _with_role("Throughput · last 30 days", bands)
    title_loc = "left"
    title_pad = SUBTITLE_TITLE_PAD if subtitle_on else THROUGHPUT_TITLE_PAD
    if identity_on:
        title_pad += IDENTITY_TITLE_PAD_BOOST
    _apply_throughput_title(
        ax, title, overload_status, overload_mode, title_loc, title_pad,
    )
    if identity_on:
        _apply_chart_identity(ax, ident, loc=title_loc, title_pad=title_pad)
    if thru_sub:
        _apply_method_subtitle(ax, thru_sub)
    _auto_spike_callout(ax, ts, write_m, read_m, bands)
    bw_handles = _throughput_legend_handles(
        adv, _events_in_span(events, ts), overload_status,
        in_legend=(overload_mode == "legend"),
    )
    _place_legend_above(ax, bw_handles, wrap_last=wrap_last)

    _plot_ratio_strip(axr, ts, read_m, write_m, events, overlays, bands)
    axr.set_title(
        _sibling_ratio_title(title, bands), loc=title_loc, pad=title_pad,
    )
    if ratio_sub:
        _apply_method_subtitle(axr, ratio_sub)
    footnote = census_footnote(bands, job.get("bands_frozen_from") or "")
    if footnote:
        fig.text(0.01, 0.012, footnote, fontsize=7.5, color=GRAY, va="bottom")

    _save_trimmed(fig, dest_path)
    return dest_path
