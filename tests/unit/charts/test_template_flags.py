"""History <img> is gated by charts_enabled / has_bandwidth_chart."""

from jinja2 import Environment, FileSystemLoader
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "allium" / "templates"


def _history_snippet():
    return (TEMPLATE_DIR / "relay-bandwidth-history.html").read_text(encoding="utf-8")


def _page_snippet():
    text = (TEMPLATE_DIR / "relay-info.html").read_text(encoding="utf-8")
    start = text.index("Network Participation")
    end = text.index("</section>", start)
    return text[start:end]


def test_template_gates_history_img():
    page = _page_snippet()
    snippet = _history_snippet()
    assert 'include "relay-bandwidth-history.html"' in page
    assert "charts_enabled|default(false) and has_bandwidth_chart|default(false)" in snippet
    assert 'src="bandwidth-1m.png"' in snippet
    assert "Throughput and write/read, last 30 days" in snippet
    assert "bandwidth_spark_periods" in snippet
    assert 'src="bandwidth-{{ period }}.png"' in snippet
    assert "href=" not in snippet
    assert snippet.index("History") < snippet.index("bandwidth-1m.png")
    assert snippet.index("bandwidth-1m.png") < snippet.index("relay-bandwidth-sparks")
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


def test_jinja_omits_sparks_when_no_charts():
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("relay-bandwidth-history.html")
    html = tmpl.render(
        charts_enabled=False,
        has_bandwidth_chart=True,
        bandwidth_spark_periods=["6m", "1y", "5y"],
    )
    assert html == ""
    assert "bandwidth-6m" not in html


def test_jinja_omits_missing_5y_spark():
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("relay-bandwidth-history.html")
    html = tmpl.render(
        charts_enabled=True,
        has_bandwidth_chart=True,
        bandwidth_spark_periods=["6m", "1y"],
    )
    assert 'src="bandwidth-1m.png"' in html
    assert 'src="bandwidth-6m.png"' in html
    assert 'src="bandwidth-1y.png"' in html
    assert "bandwidth-5y.png" not in html
