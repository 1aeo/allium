"""History chart markup: one chart per period, switched in place without JavaScript."""

from allium.lib.contact_sorting import adjust_vanity_paths
from allium.lib.page_writer import ENV

MACRO = ENV.from_string(
    '{% from "macros.html" import chart_history %}'
    '{{ chart_history(name, periods, "Uptime", src=src, ext=chart_ext) }}')


def test_every_period_has_a_target_and_a_thumbnail_link():
    html = MACRO.render(name="uptime", periods={"1m": 418, "6m": 398}, src="")
    assert html.count('class="chart-hero ') == 2
    # Each image reserves its chart's box, so a deep link lands before the lazy image loads.
    assert html.count('width="1080" height="398"') == 2 and html.count('width="1080" height="418"') == 2
    # The default (first) period comes last so "a targeted chart ~ chart" can hide it.
    assert html.index('id="uptime-6m"') < html.index('id="uptime-1m"') < html.index("chart-sparks")
    assert 'href="#uptime-1m"' in html and 'href="#uptime-6m"' in html


def test_page_wide_period_links_fall_back_to_the_default_chart():
    """#1y on a page shows each chart's 1Y, or its default chart when it has none."""
    html = MACRO.render(name="uptime", periods={"6m": 418, "1y": 418}, src="")
    assert 'class="chart-hero chart-on-1y"' in html
    assert 'class="chart-hero chart-on-6m chart-on-1m chart-on-5y"' in html
    assert 'class="chart-spark chart-on-6m chart-spark-default chart-on-1m chart-on-5y"' in html
    anchors = ENV.from_string('{% from "macros.html" import chart_period_anchors %}{{ chart_period_anchors() }}')
    assert [a for a in ("1m", "6m", "1y", "5y") if 'id="%s" class="chart-period"' % a in anchors.render()] == [
        "1m", "6m", "1y", "5y"]


def test_charts_use_the_chart_format():
    ENV.globals["chart_ext"] = "png"
    try:
        html = MACRO.render(name="uptime", periods={"1m": 418, "6m": 418}, src="")
    finally:
        ENV.globals["chart_ext"] = "svg"
    assert ".svg" not in html and html.count('uptime-1m.png"') == 3


def test_one_period_needs_no_thumbnails_and_none_renders_nothing():
    assert "chart-sparks" not in MACRO.render(name="uptime", periods={"5y": 418}, src="")
    assert MACRO.render(name="uptime", periods={}, src="").strip() == ""


def test_contact_charts_resolve_from_vanity_copies():
    html = MACRO.render(name="bandwidth", periods={"1m": 744}, src="../../contact/%s/" % ("a" * 32))
    assert 'src="../contact/%s/bandwidth-1m.svg"' % ("a" * 32) in adjust_vanity_paths(html)
