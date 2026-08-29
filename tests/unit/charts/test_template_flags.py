"""History <img> is gated by charts_enabled / has_bandwidth_chart."""

import os

from jinja2 import Environment, FileSystemLoader
from pathlib import Path

from allium.lib.charts.series import period_views
from allium.lib.page_writer import write_relay_period_files
from tests.unit.charts.conftest import FP_JEANGRAE

TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "allium" / "templates"


def _history_snippet():
    return (TEMPLATE_DIR / "relay-bandwidth-history.html").read_text(encoding="utf-8")


def _page_snippet():
    text = (TEMPLATE_DIR / "relay-info.html").read_text(encoding="utf-8")
    start = text.index('id="bandwidth"')
    end = text.index("</section>", text.index("Network Participation"))
    return text[start:end]


def test_template_gates_history_img():
    page = _page_snippet()
    snippet = _history_snippet()
    assert 'include "relay-bandwidth-history.html"' in page
    assert "charts_enabled|default(false) and has_bandwidth_chart|default(false)" in snippet
    assert 'src="bandwidth-{{ _hero }}.png"' in snippet
    assert "Throughput and write/read," in snippet
    assert "'1m': 'last 30 days'" in snippet
    assert "bandwidth_spark_periods" in snippet
    assert 'src="bandwidth-{{ period }}.png"' in snippet
    assert 'href="{{ _period_href.get(period, period + \'.html\') }}#bandwidth"' in snippet
    assert snippet.index("History") < snippet.index("bandwidth-{{ _hero }}.png")
    assert snippet.index("bandwidth-{{ _hero }}.png") < snippet.index("relay-bandwidth-sparks")
    assert 'id="bandwidth"' in page
    assert page.index('id="bandwidth"') < page.index("relay-bandwidth-history.html")
    assert page.index("Network Participation") < page.index("relay-bandwidth-history.html")


def test_jinja_omits_img_when_flags_false():
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("relay-bandwidth-history.html")
    assert tmpl.render(charts_enabled=False, has_bandwidth_chart=True) == ""
    assert tmpl.render(charts_enabled=True, has_bandwidth_chart=False) == ""
    assert tmpl.render(charts_enabled=False, has_bandwidth_chart=False) == ""
    html = tmpl.render(charts_enabled=True, has_bandwidth_chart=True)
    assert 'src="bandwidth-1m.png"' in html
    assert "last 30 days" in html


def test_jinja_omits_missing_5y_spark():
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("relay-bandwidth-history.html")
    html = tmpl.render(
        charts_enabled=True,
        has_bandwidth_chart=True,
        hero_period="1m",
        bandwidth_spark_periods=["6m", "1y"],
    )
    assert 'src="bandwidth-1m.png"' in html
    assert 'href="6m.html#bandwidth"' in html
    assert 'src="bandwidth-6m.png"' in html
    assert 'href="1y.html#bandwidth"' in html
    assert 'src="bandwidth-1y.png"' in html
    assert "bandwidth-5y.png" not in html
    assert "5y.html" not in html


def test_jinja_6m_hero_links_back_to_index():
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("relay-bandwidth-history.html")
    html = tmpl.render(
        charts_enabled=True,
        has_bandwidth_chart=True,
        hero_period="6m",
        bandwidth_spark_periods=["1m", "1y", "5y"],
    )
    assert 'src="bandwidth-6m.png"' in html
    assert html.index('src="bandwidth-6m.png"') < html.index("relay-bandwidth-sparks")
    assert 'href="index.html#bandwidth"' in html
    assert 'src="bandwidth-1m.png"' in html
    assert 'href="1y.html#bandwidth"' in html
    assert 'href="6m.html"' not in html


def test_spark_hrefs_include_history_fragment():
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("relay-bandwidth-history.html")
    index = tmpl.render(
        charts_enabled=True,
        has_bandwidth_chart=True,
        hero_period="1m",
        bandwidth_spark_periods=["6m", "1y", "5y"],
    )
    six = tmpl.render(
        charts_enabled=True,
        has_bandwidth_chart=True,
        hero_period="6m",
        bandwidth_spark_periods=["1m", "1y", "5y"],
    )
    assert 'href="6m.html#bandwidth"' in index
    assert 'href="1y.html#bandwidth"' in index
    assert 'href="5y.html#bandwidth"' in index
    assert 'href="index.html#bandwidth"' in six
    assert 'href="1y.html#bandwidth"' in six
    assert 'href="5y.html#bandwidth"' in six
    assert 'href="6m.html' not in six


def test_write_relay_period_files_emits_6m_html(temp_dir):
    env = Environment(autoescape=True)
    tmpl = env.from_string(
        "hero={{ hero_period }};"
        "{% for p in bandwidth_spark_periods %}"
        "<a href=\"{{ 'index.html' if p == '1m' else p + '.html' }}\">{{ p }}</a>"
        "{% endfor %}"
    )
    relay_dir = os.path.join(temp_dir, "relay", FP_JEANGRAE)
    write_relay_period_files(
        tmpl,
        relay_dir,
        {},
        period_views(("1m", "6m", "1y")),
        "",
        FP_JEANGRAE,
    )
    index = open(os.path.join(relay_dir, "index.html"), encoding="utf-8").read()
    six = open(os.path.join(relay_dir, "6m.html"), encoding="utf-8").read()
    year = open(os.path.join(relay_dir, "1y.html"), encoding="utf-8").read()
    assert index.startswith("hero=1m")
    assert 'href="6m.html"' in index
    assert six.startswith("hero=6m")
    assert 'href="index.html"' in six
    assert 'href="1y.html"' in six
    assert year.startswith("hero=1y")
    assert not os.path.isfile(os.path.join(relay_dir, "5y.html"))
