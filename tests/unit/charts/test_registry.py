"""Tests for ChartSpec and the period-hero registry in pipeline."""

from allium.lib.charts.pipeline import (
    PERIOD_SPEC_BY_SUFFIX,
    RELAY_BANDWIDTH_1M,
    RELAY_BANDWIDTH_PERIODS,
    ChartSpec,
    get_chart,
)


def test_period_heroes_registered():
    assert list(PERIOD_SPEC_BY_SUFFIX) == ["1m", "6m", "1y", "5y"]
    assert get_chart("not_a_chart") is None
    assert get_chart("relay_bandwidth_1m") is RELAY_BANDWIDTH_1M
    assert RELAY_BANDWIDTH_PERIODS[0] is RELAY_BANDWIDTH_1M
    fp = "AB" * 20
    for suffix, spec in PERIOD_SPEC_BY_SUFFIX.items():
        assert spec is get_chart("relay_bandwidth_%s" % suffix)
        assert spec.renderer_name == "render_relay_bandwidth_1m"
        assert spec.renderer_module == "allium.lib.charts.bandwidth"
        assert spec.renderer_version == "1"
        assert spec.cache_subdir == "relay_bandwidth_%s" % suffix
        assert spec.output_path(fp) == "relay/%s/bandwidth-%s.png" % (fp, suffix)
    spec = ChartSpec("x", "relay/{fingerprint}/x.png", "x", "m", "r", 2)
    assert spec.renderer_version == "2"
    assert spec.output_path(fp) == "relay/%s/x.png" % fp
