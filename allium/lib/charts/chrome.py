"""Shared matplotlib chrome. Import is lazy; call ``_ensure_mpl()`` in spawn."""

from .identity import IDENTITY_FONTSIZE, IDENTITY_TITLE_GAP_PT

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

THROUGHPUT_TITLE_PAD = 10
SUBTITLE_TITLE_PAD = 22
TITLE_FONTSIZE = 12.0
AXIS_FONTSIZE = 10.0
TICK_FONTSIZE = 11.0
SUBTITLE_FONTSIZE = 8.0
LEGEND_FONTSIZE = 8.5
RELAY_LINE_WEIGHT = 2.15

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
        "axes.titlesize": TITLE_FONTSIZE,
        "axes.titleweight": "bold",
        "axes.labelsize": AXIS_FONTSIZE,
        "xtick.labelsize": TICK_FONTSIZE,
        "ytick.labelsize": TICK_FONTSIZE,
        "legend.frameon": False,
        "figure.dpi": 140,
        "savefig.dpi": 140,
    })


def _trim_rgba(rgba, pad_px=12, white=250):
    """Crop outer white. Do not use savefig(bbox='tight') for this figure.

    Compare channels on the RGBA view. ``rgb.min(axis=2)`` on a strided
    ``[:,:,:3]`` slice is ~10× slower and yields the same mask.
    """
    ink = rgba[:, :, 0] < white
    ink |= rgba[:, :, 1] < white
    ink |= rgba[:, :, 2] < white
    rows = _np.flatnonzero(ink.any(axis=1))
    cols = _np.flatnonzero(ink.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        return rgba
    y0 = max(0, int(rows[0]) - pad_px)
    y1 = min(ink.shape[0], int(rows[-1]) + pad_px + 1)
    x0 = max(0, int(cols[0]) - pad_px)
    x1 = min(ink.shape[1], int(cols[-1]) + pad_px + 1)
    return rgba[y0:y1, x0:x1]


def _save_trimmed(fig, dest_path):
    import os

    fig.canvas.draw()
    rgba = _np.asarray(fig.canvas.buffer_rgba(), copy=False)
    parent = os.path.dirname(dest_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = dest_path + ".tmp.png"
    _plt.imsave(tmp, _trim_rgba(rgba))
    os.replace(tmp, dest_path)
    _plt.close(fig)


def _apply_chrome_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#bbbbbb")
    ax.spines["bottom"].set_color("#bbbbbb")
    ax.grid(True, axis="y")
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#555555", labelsize=TICK_FONTSIZE)


def _apply_chart_identity(ax, identity, loc="left", title_pad=None):
    if not identity:
        return
    pad = THROUGHPUT_TITLE_PAD if title_pad is None else title_pad
    ha = "left" if loc == "left" else "center"
    x = 0.0 if loc == "left" else 0.5
    fig = ax.figure
    # loc=left leaves ax.title empty, so the pad/fontsize fallback is what
    # we actually use. Measure via get_renderer when a center title exists;
    # do not canvas.draw() just to read an extent.
    title = ax.title
    if title is not None and title.get_text():
        title_top_px = title.get_window_extent(fig.canvas.get_renderer()).y1
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


def series_crosses_calendar_year(ts):
    return bool(ts) and ts[0].year != ts[-1].year


def date_axis_strftime(period, ts=None):
    """Tick format for the shared date axis. 5Y stays ``%Y``."""
    if period == "5y":
        return "%Y"
    if period in ("1y", "6m"):
        return "%b '%y" if series_crosses_calendar_year(ts) else "%b"
    return "%b %d"


def _date_axis(ax, period="1m", ts=None):
    fmt = date_axis_strftime(period, ts)
    if period == "5y":
        ax.xaxis.set_major_locator(_mdates.YearLocator())
    elif period == "1y":
        ax.xaxis.set_major_locator(_mdates.MonthLocator(interval=2))
    elif period == "6m":
        ax.xaxis.set_major_locator(_mdates.MonthLocator())
    else:
        ax.xaxis.set_major_locator(_mdates.WeekdayLocator(interval=1))
    ax.xaxis.set_major_formatter(_mdates.DateFormatter(fmt))
