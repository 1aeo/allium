"""History chart markup: one chart per period, switched in place without JavaScript."""

import re
from pathlib import Path
from types import SimpleNamespace

from allium.lib.charts.series import PERIODS
from allium.lib.contact_sorting import adjust_vanity_paths
from allium.lib.page_writer import ENV

BASE_CSS = Path(__file__).resolve().parents[3] / "allium" / "static" / "css" / "allium-base.css"

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
    # A thumbnail's accessible name holds its visible label (WCAG 2.5.3), so "click 1M" finds it.
    assert 'aria-label="1M: show the last 30 days"' in html
    assert ">History</h5>" in html


def test_a_chart_heading_can_name_the_chart():
    named = ENV.from_string(
        '{% from "macros.html" import chart_history %}'
        '{{ chart_history("bandwidth", {"1m": 10}, "Throughput", heading="Bandwidth") }}'
    ).render()
    assert ">Bandwidth</h5>" in named and ">History</h5>" not in named


def test_page_wide_period_links_fall_back_to_the_default_chart():
    """#1y on a page shows each chart's 1Y, or its default chart when it has none."""
    html = MACRO.render(name="uptime", periods={"6m": 418, "1y": 418}, src="")
    assert 'class="chart-hero chart-on-1y"' in html
    assert 'class="chart-hero chart-on-6m chart-on-1m chart-on-5y"' in html
    assert 'class="chart-spark chart-on-6m chart-spark-default chart-on-1m chart-on-5y"' in html
    anchors = ENV.from_string('{% from "macros.html" import chart_period_anchors %}{{ chart_period_anchors() }}')
    assert anchors.render() == "".join('<span id="%s" class="chart-period"></span>' % period for _key, period in PERIODS)
    for above in ("bandwidth", "uptime"):
        anchors = ENV.from_string('{%% from "macros.html" import chart_period_anchors %%}{{ chart_period_anchors("%s") }}'
                                  % above)
        assert anchors.render() == "".join('<span id="%s" class="chart-period chart-period-%s"></span>' % (period, above)
                                           for _key, period in PERIODS)


def test_charts_use_the_chart_format():
    html = MACRO.render(name="uptime", periods={"1m": 418, "6m": 418}, src="", chart_ext="png")
    assert ".svg" not in html and html.count('uptime-1m.png"') == 3


def test_one_period_needs_no_thumbnails_and_none_renders_nothing():
    assert "chart-sparks" not in MACRO.render(name="uptime", periods={"5y": 418}, src="")
    assert MACRO.render(name="uptime", periods={}, src="").strip() == ""


def test_an_independent_chart_keeps_its_period_off_the_url_hash():
    """Thumbnails are radios, so choosing 5Y on a second chart cannot clear the first."""
    html = ENV.from_string(
        '{% from "macros.html" import chart_history %}'
        '{{ chart_history("overload", {"1m": 10, "5y": 12}, "Overload", independent=true) }}'
        '{{ chart_history("guard", {"1m": 10, "5y": 12}, "Guard", independent=true) }}'
    ).render()
    assert html.count('name="chart-overload"') == 2 and html.count('name="chart-guard"') == 2
    assert 'id="overload-pick-5y"' in html and 'for="guard-pick-5y"' in html
    assert 'href="#overload-5y"' not in html and 'href="#guard-1m"' not in html
    assert 'id="overload-5y"' in html and 'id="guard-1m"' in html
    alone = ENV.from_string(
        '{% from "macros.html" import chart_history %}'
        '{{ chart_history("hsdir", {"1m": 10}, "HSDir", independent=true) }}'
    ).render()
    assert "chart-pick" not in alone and 'class="chart-hero ' in alone


def test_pressure_page_introduces_each_chart_and_links_to_it():
    periods = {"1m": 400, "6m": 400, "1y": 400, "5y": 400}
    html = ENV.get_template("network-pressure.html").render(
        page_ctx={"path_prefix": "", "timestamp_str": "2026-11-20 12:00"},
        relays=SimpleNamespace(timestamp="2026-11-20", pressure_periods={
            "overload": periods, "guard": periods, "hsdir": periods, "directory": periods,
        }),
    )
    assert "more anonymous, safer, and more secure" in html
    assert "CollecTor server descriptors" in html
    assert "Tor Metrics relay flags" in html
    assert "Tor Metrics dirwrite" in html
    # Nav, the intro, and the range note. Each names the period, so a jump keeps it.
    for period in ("1m", "6m", "1y", "5y"):
        assert html.count('href="#pressure-%s-overload"' % period) == 3
        assert html.count('href="#pressure-%s-directory"' % period) == 3
        assert html.count('id="pressure-%s-guard"' % period) == 1
    assert 'href="#pressure-overload"' not in html and 'href="#pressure-guard"' not in html
    # The section id can still be linked from another page. The heading itself is not a
    # fragment link: that hash would replace #5y and the charts would fall back to 1 month.
    assert 'id="network-pressure"' in html and 'href="#network-pressure"' not in html
    assert re.search(
        r'class="pressure-pill pressure-jump pressure-jump-5y"\s+href="#pressure-5y-guard"', html)
    assert re.search(r'class="pressure-jump pressure-jump-5y"\s+href="#pressure-5y-guard"', html)
    assert html.index('id="pressure-guard"') < html.index('id="pressure-5y-guard"') < html.index('id="guard-5y"')
    assert ">Relays Reporting Overload</a>" in html and ">Directory Bytes Served</a>" in html
    assert 'id="pressure-all-5y"' in html and 'for="pressure-all-5y"' in html
    assert 'name="pressure-period"' in html and 'id="pressure-all-1m">' in html
    radios = [tag for tag in re.findall(r"<input\b[^>]*>", html) if "pressure-period" in tag]
    assert len(radios) == 4 and all("checked" not in tag for tag in radios)
    assert "<script" not in html
    assert 'for="pressure-all-1m">1 month</label>' in html
    assert 'for="pressure-all-6m">6 months</label>' in html
    assert 'for="pressure-all-1y">1 year</label>' in html
    assert 'for="pressure-all-5y">5 years</label>' in html
    assert ">Time Period</div>" in html
    assert "The 1 month, 6 months, 1 year, and 5 years buttons" in html
    assert 'pressure-all-5y:checked ~ .pressure-nav label.pressure-pill[for="pressure-all-5y"]' in html
    assert html.count('name="chart-guard"') == 4
    assert "grid-template-columns: 1fr 1fr" in html
    assert ">Relays with HSDir Flag</h5>" in html
    assert "How the usual range is set" in html
    assert "Orange runs from its top up to 10%" in html
    assert "skipping days that did not finish reporting flags" in html
    missing = ENV.get_template("network-pressure.html").render(
        page_ctx={"path_prefix": "", "timestamp_str": "2026-11-20 12:00"},
        relays=SimpleNamespace(timestamp="2026-11-20", pressure_periods={"overload": periods}),
    )
    assert 'href="#pressure-1m-overload"' in missing and 'href="#pressure-5y-overload"' in missing
    assert 'id="pressure-overload"' in missing and 'id="pressure-5y-overload"' in missing
    assert 'href="#pressure-directory"' not in missing and 'href="#pressure-guard"' not in missing
    assert "pressure-keep-guard" not in missing


def _split_selector_list(argument):
    """Split a selector list on commas that are not inside parentheses."""
    parts = []
    depth = 0
    start = 0
    for index, char in enumerate(argument):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(argument[start:index])
            start = index + 1
    parts.append(argument[start:])
    return parts


def _specificity(selector):
    """CSS specificity as (ids, classes/attributes/pseudos, elements).

    ``:is()``, ``:not()``, and ``:has()`` contribute their argument's specificity,
    not their own. ``:where()`` contributes nothing.
    """
    ids = classes = elements = 0
    i = 0
    while i < len(selector):
        char = selector[i]
        if char in " \t\n\r>+~":
            i += 1
            continue
        if char == "*":
            i += 1
            continue
        if char == "#":
            ids += 1
            i += 1
            while i < len(selector) and selector[i] not in " \t\n\r>+~.#:[":
                i += 1
            continue
        if char == ".":
            classes += 1
            i += 1
            while i < len(selector) and selector[i] not in " \t\n\r>+~.#:[":
                i += 1
            continue
        if char == "[":
            classes += 1
            i = selector.index("]", i) + 1
            continue
        if char == ":":
            if selector.startswith("::", i):
                elements += 1
                i += 2
                while i < len(selector) and selector[i] not in " \t\n\r>+~.#:[(":
                    i += 1
                continue
            i += 1
            start = i
            while i < len(selector) and selector[i] not in " \t\n\r>+~.#:[(":
                i += 1
            name = selector[start:i]
            if i < len(selector) and selector[i] == "(" and name in ("is", "not", "has", "where"):
                depth = 1
                i += 1
                arg_start = i
                while i < len(selector) and depth:
                    if selector[i] == "(":
                        depth += 1
                    elif selector[i] == ")":
                        depth -= 1
                    if depth:
                        i += 1
                argument = selector[arg_start:i]
                i += 1
                if name != "where":
                    best = (0, 0, 0)
                    for part in _split_selector_list(argument):
                        best = max(best, _specificity(part))
                    ids += best[0]
                    classes += best[1]
                    elements += best[2]
                continue
            classes += 1
            continue
        elements += 1
        while i < len(selector) and selector[i] not in " \t\n\r>+~.#:[":
            i += 1
    return (ids, classes, elements)


def _rule_at(css, selector):
    """Where ``selector`` is a whole selector, not the prefix of a :hover sibling."""
    match = re.search(re.escape(selector) + r"(?!:)\s*[,{]", css)
    assert match, selector
    return match.start()


def test_a_period_fragment_paints_the_chip_until_a_radio_is_checked():
    """#5y shows five-year charts until a chip click; the click then wins, including the chip."""
    periods = {"1m": 400, "6m": 400, "1y": 400, "5y": 400}
    html = ENV.get_template("network-pressure.html").render(
        page_ctx={"path_prefix": "", "timestamp_str": "2026-11-20 12:00"},
        relays=SimpleNamespace(timestamp="2026-11-20", pressure_periods={
            "overload": periods, "guard": periods, "hsdir": periods, "directory": periods,
        }),
    )
    # One set of period anchors, earlier than the chip strip, so a fragment can style the chips.
    # Chart heroes use overload-1m and the rest, not these ids. The [id="1m"] rules are selectors.
    for period in ("1m", "6m", "1y", "5y"):
        assert html.count('<span id="%s" class="chart-period">' % period) == 1
    assert html.index('id="5y" class="chart-period"') < html.index('class="pressure-nav"')
    style = html.split("<style>", 1)[1].split("</style>", 1)[0]
    # Chart show/hide stays in allium-base.css. A copy here would follow the per-chart rules.
    assert ".chart-hero" not in style and "chart-on-" not in style

    default = '.pressure-stack .pressure-nav label[for="pressure-all-1m"]'
    undo = '.pressure-stack .chart-period:target ~ .pressure-nav label[for="pressure-all-1m"]'
    fragment = '.pressure-stack .chart-period[id="%s"]:target ~ .pressure-nav label[for="pressure-all-%s"]'
    keep_reset = '.pressure-stack:has(.pressure-keep:target) .pressure-nav label[for="pressure-all-1m"]'
    keep_chip = '.pressure-stack:has(.pressure-keep-%s:target) .pressure-nav label[for="pressure-all-%s"]'
    reset = '.pressure-stack .pressure-all:checked ~ .pressure-nav label.pressure-pill[for]'
    checked = '.pressure-stack .pressure-all-%s:checked ~ .pressure-nav label.pressure-pill[for="pressure-all-%s"]'
    # :has() is the argument's specificity, not an extra pseudo on top of it.
    assert _specificity(":has(.pressure-keep-5y:target)") == (0, 2, 0)
    assert _specificity(":where(.a, #b)") == (0, 0, 0)
    assert _specificity(":not(.a.b)") == (0, 2, 0)
    # No fragment and no checked radio: the 1 month chip is the one that looks selected.
    assert _specificity(default) == (0, 3, 1)
    assert ":target" not in default and ":checked" not in default
    # A period fragment beats that default, including when the fragment is #1m.
    assert _specificity(undo) == (0, 5, 1)
    assert _specificity(fragment % ("1m", "1m")) == (0, 6, 1)
    assert _specificity(fragment % ("5y", "5y")) == (0, 6, 1)
    # A jump anchor paints the same chip, but lighter than a checked radio.
    assert _specificity(keep_reset) == (0, 5, 1)
    assert _specificity(keep_chip % ("1m", "1m")) == (0, 5, 1)
    assert _specificity(keep_chip % ("5y", "5y")) == (0, 5, 1)
    # A checked chip ties the fragment and is later, so a click after #5y moves the strip.
    # It also outweighs the jump-anchor chip.
    assert _specificity(reset) == (0, 6, 1)
    assert _specificity(checked % ("1m", "1m")) == (0, 6, 1)
    assert _specificity(checked % ("5y", "5y")) == (0, 6, 1)
    assert fragment % ("5y", "5y") + ":hover" not in style
    order = [
        _rule_at(style, default),
        _rule_at(style, undo),
        _rule_at(style, fragment % ("1m", "1m")),
        _rule_at(style, fragment % ("6m", "6m")),
        _rule_at(style, fragment % ("1y", "1y")),
        _rule_at(style, fragment % ("5y", "5y")),
        _rule_at(style, keep_reset),
        _rule_at(style, keep_chip % ("1m", "1m")),
        _rule_at(style, keep_chip % ("6m", "6m")),
        _rule_at(style, keep_chip % ("1y", "1y")),
        _rule_at(style, keep_chip % ("5y", "5y")),
        _rule_at(style, reset),
        _rule_at(style, checked % ("1m", "1m")),
        _rule_at(style, checked % ("6m", "6m")),
        _rule_at(style, checked % ("1y", "1y")),
        _rule_at(style, checked % ("5y", "5y")),
    ]
    assert order == sorted(order)

    # The visible jump set follows the fragment, then the jump anchor, then a checked radio.
    jump_rest = ".pressure-stack .pressure-jump-1m"
    jump_hide = ".pressure-stack:has(.pressure-keep:target) .pressure-jump"
    jump_fragment = '.pressure-stack:has(.chart-period[id="5y"]:target) .pressure-jump-5y'
    jump_keep = ".pressure-stack:has(.pressure-keep-5y:target) .pressure-jump-5y"
    jump_checked_hide = ".pressure-stack:has(.pressure-all:checked) .pressure-jump.pressure-jump"
    jump_checked = ".pressure-stack:has(.pressure-all-6m:checked) .pressure-jump.pressure-jump-6m"
    assert _specificity(jump_rest) == (0, 2, 0)
    assert _specificity(jump_hide) == (0, 4, 0) == _specificity(jump_keep)
    assert _specificity(jump_fragment) == (0, 5, 0)
    assert _specificity(jump_checked_hide) == (0, 5, 0) == _specificity(jump_checked)
    jump_order = [
        _rule_at(style, jump_rest),
        _rule_at(style, jump_hide),
        _rule_at(style, jump_fragment),
        _rule_at(style, jump_keep),
        _rule_at(style, jump_checked_hide),
        _rule_at(style, jump_checked),
    ]
    assert jump_order == sorted(jump_order)

    css = BASE_CSS.read_text()
    target = '.chart-period[id="5y"]:target ~ * .chart-hero.chart-on-5y'
    keep_hide = "body:has(.pressure-keep:target) .chart-hero"
    keep_show = "body:has(.pressure-keep-5y:target) .chart-hero.chart-on-5y"
    shared_hide = '.pressure-all:checked ~ .pressure-charts .chart-hero.chart-hero'
    shared_show = '.pressure-all-1m:checked ~ .pressure-charts .chart-hero.chart-on-1m'
    own = '.chart-history.chart-history .chart-pick-5y:checked ~ .chart-hero.chart-hero.chart-on-5y'
    # A jump anchor is lighter than a checked radio, which is later. The chart's own
    # radio repeats .chart-history on the same element (not a descendant) and outranks both.
    assert _specificity(target) == (0, 5, 0)
    assert _specificity(keep_hide) == (0, 3, 1)
    assert _specificity(keep_show) == (0, 4, 1)
    assert _specificity(shared_hide) == (0, 5, 0) == _specificity(shared_show)
    assert _specificity(own) == (0, 7, 0)
    assert ".chart-history .chart-history" not in css
    assert _rule_at(css, target) < _rule_at(css, keep_hide) < _rule_at(css, keep_show)
    assert _rule_at(css, keep_show) < _rule_at(css, shared_hide) < _rule_at(css, shared_show) < _rule_at(css, own)


def test_contact_charts_resolve_from_vanity_copies():
    html = MACRO.render(name="bandwidth", periods={"1m": 744}, src="../../contact/%s/" % ("a" * 32))
    assert 'src="../contact/%s/bandwidth-1m.svg"' % ("a" * 32) in adjust_vanity_paths(html)
