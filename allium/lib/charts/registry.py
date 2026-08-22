"""Chart type registry.

Adding a chart is a new ChartSpec + a renderer + a later template slot.
Shared across types: cache, process pool, output layout, progress.
"""

from collections import OrderedDict

RELAY_BANDWIDTH_1M_ID = "relay_bandwidth_1m"


class ChartSpec(object):
    """Small immutable description of one chart type."""

    __slots__ = (
        "chart_id",
        "page_slot",
        "onionoo_inputs",
        "period",
        "output_path_pattern",
        "cache_subdir",
        "renderer_module",
        "renderer_name",
        "renderer_version",
        "locked_style",
        "enabled",
    )

    def __init__(
        self,
        chart_id,
        page_slot,
        onionoo_inputs,
        period,
        output_path_pattern,
        cache_subdir,
        renderer_module,
        renderer_name,
        renderer_version,
        locked_style,
        enabled=True,
    ):
        self.chart_id = chart_id
        self.page_slot = page_slot
        self.onionoo_inputs = tuple(onionoo_inputs)
        self.period = period
        self.output_path_pattern = output_path_pattern
        self.cache_subdir = cache_subdir
        self.renderer_module = renderer_module
        self.renderer_name = renderer_name
        self.renderer_version = str(renderer_version)
        self.locked_style = locked_style
        self.enabled = bool(enabled)

    def output_path(self, fingerprint):
        """Relative path under the site output root for this fingerprint."""
        return self.output_path_pattern.format(fingerprint=fingerprint)


# First — and until more renderers exist, only — registered chart.
RELAY_BANDWIDTH_1M = ChartSpec(
    chart_id=RELAY_BANDWIDTH_1M_ID,
    page_slot="relay#bandwidth",
    onionoo_inputs=("details", "bandwidth"),
    period="1_month",
    output_path_pattern="relay/{fingerprint}/bandwidth-1m.png",
    cache_subdir="relay_bandwidth_1m",
    renderer_module="allium.lib.charts.bandwidth",
    renderer_name="render_relay_bandwidth_1m",
    renderer_version="1",
    locked_style="style5_option_c",
    enabled=True,
)

# OrderedDict so enabled_charts() is stable for tests and progress logs.
_REGISTRY = OrderedDict((
    (RELAY_BANDWIDTH_1M.chart_id, RELAY_BANDWIDTH_1M),
))


def get_chart(chart_id):
    """Return a ChartSpec or None."""
    return _REGISTRY.get(chart_id)


def registered_chart_ids():
    """All registered ids, including disabled specs."""
    return tuple(_REGISTRY.keys())


def enabled_charts():
    """Specs the chart pass should consider, in registry order."""
    return tuple(spec for spec in _REGISTRY.values() if spec.enabled)
