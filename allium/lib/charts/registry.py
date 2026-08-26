"""Chart type registry. Shared: cache, process pool, output layout."""

from collections import OrderedDict

RELAY_BANDWIDTH_1M_ID = "relay_bandwidth_1m"


class ChartSpec(object):
    __slots__ = (
        "chart_id",
        "output_path_pattern",
        "cache_subdir",
        "renderer_module",
        "renderer_name",
        "renderer_version",
        "enabled",
    )

    def __init__(
        self,
        chart_id,
        output_path_pattern,
        cache_subdir,
        renderer_module,
        renderer_name,
        renderer_version,
        enabled=True,
    ):
        self.chart_id = chart_id
        self.output_path_pattern = output_path_pattern
        self.cache_subdir = cache_subdir
        self.renderer_module = renderer_module
        self.renderer_name = renderer_name
        self.renderer_version = str(renderer_version)
        self.enabled = bool(enabled)

    def output_path(self, fingerprint):
        return self.output_path_pattern.format(fingerprint=fingerprint)


RELAY_BANDWIDTH_1M = ChartSpec(
    chart_id=RELAY_BANDWIDTH_1M_ID,
    output_path_pattern="relay/{fingerprint}/bandwidth-1m.png",
    cache_subdir="relay_bandwidth_1m",
    renderer_module="allium.lib.charts.bandwidth",
    renderer_name="render_relay_bandwidth_1m",
    renderer_version="1",
    enabled=True,
)

_REGISTRY = OrderedDict((
    (RELAY_BANDWIDTH_1M.chart_id, RELAY_BANDWIDTH_1M),
))


def get_chart(chart_id):
    return _REGISTRY.get(chart_id)


def registered_chart_ids():
    return tuple(_REGISTRY.keys())


def enabled_charts():
    return tuple(spec for spec in _REGISTRY.values() if spec.enabled)
