"""History chart markup: one chart per period, switched in place without JavaScript."""

from allium.lib.contact_sorting import adjust_vanity_paths
from allium.lib.page_writer import ENV

MACRO = ENV.from_string(
    '{% from "macros.html" import chart_history %}'
    '{{ chart_history(name, periods, "Uptime", src=src) }}')


def test_every_period_has_a_target_and_a_thumbnail_link():
    html = MACRO.render(name="uptime", periods=("1m", "6m"), src="")
    assert html.count('class="chart-hero"') == 2
    # The default (first) period comes last so "a targeted chart ~ chart" can hide it.
    assert html.index('id="uptime-6m"') < html.index('id="uptime-1m"') < html.index("chart-sparks")
    assert 'href="#uptime-1m"' in html and 'href="#uptime-6m"' in html


def test_one_period_needs_no_thumbnails_and_none_renders_nothing():
    assert "chart-sparks" not in MACRO.render(name="uptime", periods=("5y",), src="")
    assert MACRO.render(name="uptime", periods=(), src="").strip() == ""


def test_contact_charts_resolve_from_vanity_copies():
    html = MACRO.render(name="bandwidth", periods=("1m",), src="../../contact/%s/" % ("a" * 32))
    assert 'src="../contact/%s/bandwidth-1m.svg"' % ("a" * 32) in adjust_vanity_paths(html)
