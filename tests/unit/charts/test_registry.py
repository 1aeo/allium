"""Tests for ChartSpec and the period-hero registry in pipeline."""

from allium.lib.charts.pipeline import (
    CONTACT_BANDWIDTH_1M,
    CONTACT_PERIOD_SPEC_BY_SUFFIX,
    PERIOD_SPEC_BY_SUFFIX,
    RELAY_BANDWIDTH_1M,
    RELAY_BANDWIDTH_PERIODS,
    RELAY_UPTIME_1M,
    RELAY_UPTIME_PERIODS,
    UPTIME_SPEC_BY_SUFFIX,
    ChartSpec,
    get_chart,
)
from tests.unit.charts.conftest import CONTACT_A


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
        assert spec.renderer_version == "3"
        assert spec.cache_subdir == "relay_bandwidth_%s" % suffix
        assert spec.output_path(fp) == "relay/%s/bandwidth-%s.png" % (fp, suffix)
    spec = ChartSpec("x", "relay/{fingerprint}/x.png", "x", "m", "r", 2)
    assert spec.renderer_version == "2"
    assert spec.output_path(fp) == "relay/%s/x.png" % fp


def test_uptime_heroes_registered():
    assert list(UPTIME_SPEC_BY_SUFFIX) == ["1m", "6m", "1y", "5y"]
    assert get_chart("relay_uptime_1m") is RELAY_UPTIME_1M
    assert RELAY_UPTIME_PERIODS[0] is RELAY_UPTIME_1M
    fp = "AB" * 20
    for suffix, spec in UPTIME_SPEC_BY_SUFFIX.items():
        assert spec is get_chart("relay_uptime_%s" % suffix)
        assert spec.renderer_name == "render_relay_uptime"
        assert spec.renderer_module == "allium.lib.charts.uptime"
        assert spec.renderer_version == "1"
        assert spec.cache_subdir == "relay_uptime_%s" % suffix
        assert spec.output_path(fp) == "relay/%s/uptime-%s.png" % (fp, suffix)
    assert get_chart("relay_uptime_1m") is not get_chart("relay_bandwidth_1m")


def test_contact_period_specs_use_contact_md5_paths():
    assert list(CONTACT_PERIOD_SPEC_BY_SUFFIX) == ["1m", "6m", "1y", "5y"]
    assert get_chart("contact_bandwidth_1m") is CONTACT_BANDWIDTH_1M
    hid = CONTACT_A
    for suffix, spec in CONTACT_PERIOD_SPEC_BY_SUFFIX.items():
        assert spec is get_chart("contact_bandwidth_%s" % suffix)
        assert spec.renderer_name == "render_relay_bandwidth_1m"
        assert spec.cache_subdir == "contact_bandwidth_%s" % suffix
        assert spec.output_path(hid) == "contact/%s/bandwidth-%s.png" % (hid, suffix)
        assert spec.output_path(hid).startswith("contact/")
        assert "relay/" not in spec.output_path(hid)
