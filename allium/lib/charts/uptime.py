"""Relay uptime renderer. Matplotlib is imported in ``_ensure_mpl()`` only."""

from ..uptime_utils import _compute_uptime_percentage_and_datapoints
from .bandwidth import (
    AXIS_FONTSIZE,
    CHROME_WEIGHTS,
    GRAY,
    GREEN,
    TITLE_FONTSIZE,
    THROUGHPUT_TITLE_PAD,
    SUBTITLE_TITLE_PAD,
    _apply_chart_identity,
    _apply_chrome_axes,
    _apply_method_subtitle,
    _apply_style,
    _date_axis,
    _draw_event_lines,
    _ensure_mpl,
    _event_legend_handles,
    _events_in_span,
    _pad_xlim,
    _place_legend_above,
    _save_trimmed,
    restart_events,
)
from .identity import (
    IDENTITY_EXTRA_FIG_H,
    IDENTITY_TITLE_PAD_BOOST,
    IDENTITY_TOP_SHIFT,
    chart_identity,
)
from .series import (
    MIN_ALIGNED_POINTS,
    PERIOD_TITLE_SPAN,
    period_axis_caption,
    uptime_percent_series,
)


def render_relay_uptime(job, dest_path):
    """Draw a single-axis uptime figure and write ``dest_path``.

    Distinct from the bandwidth dual-panel hero: percent 0–100, no
    write/read ratio bands. ``job`` is a slim picklable dict. Raises
    ``ValueError`` when history is too thin to draw.
    """
    from . import bandwidth as chrome

    plt = _ensure_mpl()
    _apply_style(plt)

    period = job.get("period") or "1m"
    block = job.get("uptime")
    ts, pct = uptime_percent_series(block)
    if len(ts) < MIN_ALIGNED_POINTS:
        raise ValueError("thin or missing uptime history")

    events = _events_in_span(restart_events(job.get("last_restarted")), ts)
    nickname = job.get("nickname") or ""
    operator = job.get("operator") or ""
    ident = chart_identity(nickname, operator)
    identity_on = bool(ident)
    avg, n_pts = _compute_uptime_percentage_and_datapoints(
        (block or {}).get("values") or [],
    )
    subtitle = ""
    if n_pts >= 30 and avg:
        subtitle = "Average {:.1f}%  ·  Onionoo Running flag".format(avg)
    subtitle_on = bool(subtitle)

    fig_h = 4.35 if subtitle_on else 4.15
    top = 0.82 if subtitle_on else 0.88
    title_pad = SUBTITLE_TITLE_PAD if subtitle_on else THROUGHPUT_TITLE_PAD
    if identity_on:
        fig_h += IDENTITY_EXTRA_FIG_H
        top = max(0.70, top - IDENTITY_TOP_SHIFT)
        title_pad += IDENTITY_TITLE_PAD_BOOST

    fig, ax = plt.subplots(1, 1, figsize=(10.8, fig_h))
    fig.subplots_adjust(top=top, bottom=0.18)

    ax.plot(ts, pct, color=GREEN, linewidth=CHROME_WEIGHTS["relay"])
    _draw_event_lines(ax, events, lw=CHROME_WEIGHTS["restart"])
    _apply_chrome_axes(ax)
    _pad_xlim(ax, ts)
    ax.set_ylim(0, 112)
    ax.set_ylabel("Uptime (%)", fontsize=AXIS_FONTSIZE)
    _date_axis(ax, period, ts)
    if period != "1m":
        ax.set_xlabel(period_axis_caption(period, block), fontsize=AXIS_FONTSIZE)

    title = "Uptime  ·  {}".format(PERIOD_TITLE_SPAN.get(period) or period)
    ax.set_title(title, loc="left", pad=title_pad, fontsize=TITLE_FONTSIZE)
    if identity_on:
        _apply_chart_identity(ax, ident, loc="left", title_pad=title_pad)
    if subtitle:
        _apply_method_subtitle(ax, subtitle)

    Line2D = chrome._Line2D
    handles = [
        Line2D([0], [0], color=GREEN, linewidth=1.8, label="Running flag"),
    ]
    handles.extend(_event_legend_handles(events))
    if n_pts >= 30 and avg:
        handles.append(Line2D(
            [0], [0], color=GRAY, linestyle="None",
            label="Average  {:.1f}%".format(avg),
        ))
    _place_legend_above(ax, handles)

    _save_trimmed(fig, dest_path)
    return dest_path
