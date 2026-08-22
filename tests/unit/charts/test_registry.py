"""Tests for the chart type registry."""

from allium.lib.charts.registry import (
    RELAY_BANDWIDTH_1M,
    RELAY_BANDWIDTH_1M_ID,
    ChartSpec,
    enabled_charts,
    get_chart,
    registered_chart_ids,
)


def test_relay_bandwidth_1m_is_registered():
    spec = get_chart(RELAY_BANDWIDTH_1M_ID)
    assert spec is RELAY_BANDWIDTH_1M
    assert spec.chart_id == "relay_bandwidth_1m"
    assert spec.page_slot == "relay#bandwidth"
    assert spec.onionoo_inputs == ("details", "bandwidth")
    assert spec.period == "1_month"
    assert spec.output_path_pattern == "relay/{fingerprint}/bandwidth-1m.png"
    assert spec.cache_subdir == "relay_bandwidth_1m"
    assert spec.renderer_module == "allium.lib.charts.bandwidth"
    assert spec.renderer_name == "render_relay_bandwidth_1m"
    assert spec.renderer_version == "1"
    assert spec.locked_style == "style5_option_c"
    assert spec.enabled is True


def test_output_path_uses_fingerprint():
    path = RELAY_BANDWIDTH_1M.output_path("02B1C5DFBCBEC735435652050DE1AF0BB0B108CF")
    assert path == (
        "relay/02B1C5DFBCBEC735435652050DE1AF0BB0B108CF/bandwidth-1m.png"
    )


def test_unknown_chart_id_returns_none():
    assert get_chart("not_a_chart") is None


def test_enabled_charts_is_only_bandwidth_1m():
    charts = enabled_charts()
    assert [spec.chart_id for spec in charts] == [RELAY_BANDWIDTH_1M_ID]
    assert registered_chart_ids() == (RELAY_BANDWIDTH_1M_ID,)


def test_chart_spec_onionoo_inputs_are_a_tuple():
    spec = ChartSpec(
        chart_id="x",
        page_slot="relay#x",
        onionoo_inputs=["details"],
        period="1_month",
        output_path_pattern="relay/{fingerprint}/x.png",
        cache_subdir="x",
        renderer_module="m",
        renderer_name="r",
        renderer_version=2,
        locked_style="s",
        enabled=False,
    )
    assert spec.onionoo_inputs == ("details",)
    assert spec.renderer_version == "2"
    assert spec.enabled is False
