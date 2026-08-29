"""Tests for the chart type registry."""

from allium.lib.charts.registry import (
    PERIOD_SPEC_BY_SUFFIX,
    RELAY_BANDWIDTH_1M,
    RELAY_BANDWIDTH_1M_ID,
    RELAY_BANDWIDTH_PERIODS,
    ChartSpec,
    enabled_charts,
    get_chart,
    registered_chart_ids,
)


def test_relay_bandwidth_1m_is_registered():
    spec = get_chart(RELAY_BANDWIDTH_1M_ID)
    assert spec is RELAY_BANDWIDTH_1M
    assert spec.chart_id == "relay_bandwidth_1m"
    assert spec.output_path_pattern == "relay/{fingerprint}/bandwidth-1m.png"
    assert spec.cache_subdir == "relay_bandwidth_1m"
    assert spec.renderer_module == "allium.lib.charts.bandwidth"
    assert spec.renderer_name == "render_relay_bandwidth_1m"
    assert spec.renderer_version == "1"
    assert spec.enabled is True


def test_output_path_uses_fingerprint():
    path = RELAY_BANDWIDTH_1M.output_path("02B1C5DFBCBEC735435652050DE1AF0BB0B108CF")
    assert path == (
        "relay/02B1C5DFBCBEC735435652050DE1AF0BB0B108CF/bandwidth-1m.png"
    )


def test_unknown_chart_id_returns_none():
    assert get_chart("not_a_chart") is None


def test_four_period_heroes_are_registered():
    assert list(PERIOD_SPEC_BY_SUFFIX) == ["1m", "6m", "1y", "5y"]
    assert registered_chart_ids() == (
        "relay_bandwidth_1m",
        "relay_bandwidth_6m",
        "relay_bandwidth_1y",
        "relay_bandwidth_5y",
    )
    assert enabled_charts() == RELAY_BANDWIDTH_PERIODS
    assert RELAY_BANDWIDTH_PERIODS[0] is RELAY_BANDWIDTH_1M
    for suffix, spec in PERIOD_SPEC_BY_SUFFIX.items():
        assert get_chart("relay_bandwidth_%s" % suffix) is spec
        assert spec.renderer_name == "render_relay_bandwidth_1m"
        assert spec.output_path("AB" * 20) == (
            "relay/%s/bandwidth-%s.png" % ("AB" * 20, suffix)
        )


def test_chart_spec_onionoo_inputs_are_a_tuple():
    spec = ChartSpec(
        chart_id="x",
        output_path_pattern="relay/{fingerprint}/x.png",
        cache_subdir="x",
        renderer_module="m",
        renderer_name="r",
        renderer_version=2,
        enabled=False,
    )
    assert spec.renderer_version == "2"
    assert spec.enabled is False
