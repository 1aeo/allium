"""Priority-flag presence over time. Matplotlib stays in shared chrome."""

from ..flag_analysis import FLAG_DISPLAY_NAMES
from .chrome import (
    BLUE,
    RELAY_LINE_WEIGHT,
    TITLE_FONTSIZE,
    THROUGHPUT_TITLE_PAD,
    _apply_chart_identity,
    _apply_chrome_axes,
    _apply_style,
    _date_axis,
    _ensure_mpl,
    _pad_xlim,
    _save_trimmed,
)
from .identity import (
    IDENTITY_EXTRA_FIG_H,
    IDENTITY_TITLE_PAD_BOOST,
    IDENTITY_TOP_SHIFT,
    chart_identity,
)
from .series import MIN_ALIGNED_POINTS, PERIOD_TITLE_SPAN, flag_percent_series


def render_relay_flags(job, dest_path):
    """Draw one priority-flag presence series and write ``dest_path``."""
    plt = _ensure_mpl()
    _apply_style(plt)

    period = job.get("period") or "1m"
    ts, perc = flag_percent_series(job.get("history"))
    if len(ts) < MIN_ALIGNED_POINTS:
        raise ValueError("thin or missing flag history")

    flag = job.get("flag") or ""
    display = FLAG_DISPLAY_NAMES.get(flag, flag or "Flag")
    ident = chart_identity(job.get("nickname"), job.get("operator"))
    identity_on = bool(ident)

    fig_h = 4.2
    top = 0.86
    title_pad = THROUGHPUT_TITLE_PAD
    if identity_on:
        fig_h += IDENTITY_EXTRA_FIG_H
        top = max(0.70, top - IDENTITY_TOP_SHIFT)
        title_pad += IDENTITY_TITLE_PAD_BOOST
    fig, ax = plt.subplots(figsize=(10.8, fig_h))
    fig.subplots_adjust(top=top, bottom=0.18, left=0.08, right=0.98)

    ax.plot(ts, perc, color=BLUE, linewidth=RELAY_LINE_WEIGHT, solid_capstyle="round")
    ax.set_ylim(0, 105)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("Presence %")
    title = "{} flag presence · {}".format(
        display, PERIOD_TITLE_SPAN.get(period) or period,
    )
    ax.set_title(title, loc="left", pad=title_pad, fontsize=TITLE_FONTSIZE)
    if identity_on:
        _apply_chart_identity(ax, ident, loc="left", title_pad=title_pad)
    _apply_chrome_axes(ax)
    _date_axis(ax, period, ts)
    _pad_xlim(ax, ts)
    _save_trimmed(fig, dest_path)
    return dest_path
