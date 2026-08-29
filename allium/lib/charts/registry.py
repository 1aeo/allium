"""Chart type registry. Shared: cache, process pool, output layout."""

from collections import OrderedDict

from .series import PERIOD_KEYS

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


def _bandwidth_spec(suffix):
    return ChartSpec(
        chart_id="relay_bandwidth_%s" % suffix,
        output_path_pattern="relay/{fingerprint}/bandwidth-%s.png" % suffix,
        cache_subdir="relay_bandwidth_%s" % suffix,
        renderer_module="allium.lib.charts.bandwidth",
        renderer_name="render_relay_bandwidth_1m",
        renderer_version="1",
        enabled=True,
    )


PERIOD_SPEC_BY_SUFFIX = OrderedDict(
    (suffix, _bandwidth_spec(suffix)) for _onionoo, suffix in PERIOD_KEYS
)
RELAY_BANDWIDTH_1M = PERIOD_SPEC_BY_SUFFIX["1m"]
RELAY_BANDWIDTH_PERIODS = tuple(PERIOD_SPEC_BY_SUFFIX.values())

_REGISTRY = OrderedDict(
    (spec.chart_id, spec) for spec in RELAY_BANDWIDTH_PERIODS
)


def get_chart(chart_id):
    return _REGISTRY.get(chart_id)


def registered_chart_ids():
    return tuple(_REGISTRY.keys())


def enabled_charts():
    return tuple(spec for spec in _REGISTRY.values() if spec.enabled)
