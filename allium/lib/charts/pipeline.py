"""Chart-pass entry point.

Default is off and silent so the ~5 minute HTML generate is unchanged.
matplotlib must not be imported here — only probed via find_spec.
"""

import importlib
import importlib.util
import os

from .registry import enabled_charts

CHARTS_OFF = "off"
CHARTS_AUTO = "auto"
CHARTS_ON = "on"
CHARTS_MODES = (CHARTS_OFF, CHARTS_AUTO, CHARTS_ON)

# Shown when --charts on/auto cannot run. Always printed (not --progress
# only) so an operator who asked for charts sees why PNGs are missing.
_INSTALL_HINT = (
    "Charts: skipped (matplotlib not installed; "
    "pip install -r config/requirements-charts.txt)"
)
_RENDERER_HINT = "Charts: skipped (renderer not implemented; HTML unchanged)"
_AUTO_HINT = "Charts: skipped (auto; extra or renderer missing)"
_NO_BANDWIDTH_HINT = "Charts: skipped (no bandwidth data; use --apis all)"


class ChartRunResult(object):
    """Outcome of maybe_run_charts(). No figures are drawn yet."""

    def __init__(self, status, reason, charts_mode=CHARTS_OFF):
        self.status = status
        self.reason = reason
        self.charts_mode = charts_mode

    def __repr__(self):
        return "ChartRunResult(status={!r}, reason={!r}, charts_mode={!r})".format(
            self.status, self.reason, self.charts_mode
        )


def add_chart_arguments(parser):
    """Register --charts / --no-charts / --chart-workers on the CLI parser.

    Default is off so the 5-minute HTML generate stays unchanged until
    the renderer exists. ``--charts`` with no value means on.
    """
    parser.add_argument(
        "--charts",
        dest="charts",
        nargs="?",
        const=CHARTS_ON,
        choices=list(CHARTS_MODES),
        default=CHARTS_OFF,
        help=(
            "generate relay-page charts after HTML "
            "(off, auto, on; default: off). "
            "auto enables only when the charts extra is installed"
        ),
        required=False,
    )
    parser.add_argument(
        "--no-charts",
        dest="charts",
        action="store_const",
        const=CHARTS_OFF,
        help="skip chart generation (default)",
        required=False,
    )
    parser.add_argument(
        "--chart-workers",
        dest="chart_workers",
        type=int,
        default=0,
        help=(
            "process-pool size for chart render "
            "(default: min(4, CPU count); 0 = auto)"
        ),
        required=False,
    )


def resolve_charts_mode(args):
    """Return off/auto/on from an argparse namespace."""
    mode = getattr(args, "charts", CHARTS_OFF) or CHARTS_OFF
    if mode not in CHARTS_MODES:
        return CHARTS_OFF
    return mode


def default_chart_workers(override=0):
    """Small process-pool cap. Do not reuse --workers (often 8–16)."""
    if override and int(override) > 0:
        return int(override)
    cpu = os.cpu_count() or 1
    return max(1, min(4, cpu))


def matplotlib_is_available():
    """True when the charts extra is installed. Does not import pyplot."""
    return importlib.util.find_spec("matplotlib") is not None


def renderer_is_ready(spec):
    """True when the spec's render function exists and is callable."""
    try:
        module = importlib.import_module(spec.renderer_module)
    except ImportError:
        return False
    func = getattr(module, spec.renderer_name, None)
    return callable(func)


def _emit(message, progress_logger=None):
    print(message)
    if progress_logger is not None:
        log = getattr(progress_logger, "log_without_increment", None)
        if callable(log):
            log(message)


def maybe_run_charts(relay_set, args, progress_logger=None):
    """Run or skip the chart pass. Safe to call after generate_site().

    Default ``--charts off`` returns immediately with no log line and
    does not touch relay_set. Missing extra / renderer never fails the
    HTML generate.
    """
    mode = resolve_charts_mode(args)
    if mode == CHARTS_OFF:
        return ChartRunResult(status="skipped", reason="off", charts_mode=mode)

    specs = [spec for spec in enabled_charts() if renderer_is_ready(spec)]
    extra_ok = matplotlib_is_available()

    if mode == CHARTS_AUTO and (not extra_ok or not specs):
        _emit(_AUTO_HINT, progress_logger)
        return ChartRunResult(
            status="skipped",
            reason="auto_unavailable",
            charts_mode=mode,
        )

    if not extra_ok:
        _emit(_INSTALL_HINT, progress_logger)
        return ChartRunResult(
            status="skipped",
            reason="matplotlib_missing",
            charts_mode=mode,
        )

    if not specs:
        _emit(_RENDERER_HINT, progress_logger)
        return ChartRunResult(
            status="skipped",
            reason="renderer_missing",
            charts_mode=mode,
        )

    bandwidth_data = getattr(relay_set, "bandwidth_data", None) if relay_set else None
    if not bandwidth_data:
        _emit(_NO_BANDWIDTH_HINT, progress_logger)
        return ChartRunResult(
            status="skipped",
            reason="no_bandwidth_data",
            charts_mode=mode,
        )

    # Renderer exists in a later turn. Keep this branch explicit so a
    # half-implemented extra cannot start a pool by accident.
    _emit(_RENDERER_HINT, progress_logger)
    return ChartRunResult(
        status="skipped",
        reason="renderer_not_wired",
        charts_mode=mode,
    )
