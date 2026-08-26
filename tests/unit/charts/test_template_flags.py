"""History <img> is gated by charts_enabled / has_bandwidth_chart."""

from jinja2 import Environment, FileSystemLoader
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "allium" / "templates"


def _history_snippet():
    text = (TEMPLATE_DIR / "relay-info.html").read_text(encoding="utf-8")
    start = text.index("Network Participation")
    end = text.index("</section>", start)
    return text[start:end]


def test_template_gates_history_img():
    snippet = _history_snippet()
    assert "charts_enabled|default(false) and has_bandwidth_chart|default(false)" in snippet
    assert 'src="bandwidth-1m.png"' in snippet
    assert "Throughput and write/read, last 30 days" in snippet
    # History sits after Network Participation, still inside #bandwidth.
    assert snippet.index("Network Participation") < snippet.index("History")
    assert snippet.index("History") < snippet.index("bandwidth-1m.png")


def test_jinja_omits_img_when_flags_false():
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    # Render just the condition the way the page does.
    tmpl = env.from_string(
        "{% if charts_enabled and has_bandwidth_chart %}"
        "<img src=\"bandwidth-1m.png\" alt=\"Throughput and write/read, last 30 days\">"
        "{% endif %}"
    )
    assert tmpl.render(charts_enabled=False, has_bandwidth_chart=True) == ""
    assert tmpl.render(charts_enabled=True, has_bandwidth_chart=False) == ""
    assert tmpl.render(charts_enabled=False, has_bandwidth_chart=False) == ""
    html = tmpl.render(charts_enabled=True, has_bandwidth_chart=True)
    assert 'src="bandwidth-1m.png"' in html
