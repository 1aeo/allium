"""Where the chart files go, and how relay, contact and vanity-domain pages reference them, in either --chart-layout."""

import os
import re
import time
from datetime import datetime, timezone

import pytest

from allium.lib import page_writer, time_utils
from allium.lib.charts.render import CHARTS_DIR, clear_chart_tree
from allium.lib.relays import Relays

from .fixtures import history, writer

PUBLISHED = "2026-09-30 12:00:00"
FPS = ("A" * 40, "B" * 40, "C" * 40)  # one operator's relays: enough for its sort variants and vanity copy
DOMAIN = "example.org"
CHART = re.compile(r"(?:bandwidth|uptime)-(?:1m|6m|1y|5y)\.svg")
CHART_REF = re.compile(r'(?:src|href)="([^"]*\.svg)"')
LINK = re.compile(r'(src|href)="([^"]*)"')
NOW = datetime(2026, 9, 30, 12, 30, tzinfo=timezone.utc)  # the build's clock: the pages show times and ages from it
# _chart_links of a beside build: the files and chart links master wrote before --chart-layout. {A}, {B} and {C} stand
# for the relays' fingerprints, {h} for the contact's hash. A change meant to move a chart or a link updates this list;
# the failed assertion shows which line changed. Other edits to these pages do not touch it.
BESIDE = """\
contact/{h}/bandwidth-1m.svg
contact/{h}/bandwidth-6m.svg
contact/{h}/index.html: href=../../contact/{h}/bandwidth-1m.svg
contact/{h}/index.html: href=../../contact/{h}/bandwidth-6m.svg
contact/{h}/index.html: href=../../contact/{h}/uptime-1m.svg
contact/{h}/index.html: src=../../contact/{h}/bandwidth-1m.svg
contact/{h}/index.html: src=../../contact/{h}/bandwidth-1m.svg
contact/{h}/index.html: src=../../contact/{h}/bandwidth-6m.svg
contact/{h}/index.html: src=../../contact/{h}/bandwidth-6m.svg
contact/{h}/index.html: src=../../contact/{h}/uptime-1m.svg
contact/{h}/uptime-1m.svg
example.org/index.html: href=../contact/{h}/bandwidth-1m.svg
example.org/index.html: href=../contact/{h}/bandwidth-6m.svg
example.org/index.html: href=../contact/{h}/uptime-1m.svg
example.org/index.html: src=../contact/{h}/bandwidth-1m.svg
example.org/index.html: src=../contact/{h}/bandwidth-1m.svg
example.org/index.html: src=../contact/{h}/bandwidth-6m.svg
example.org/index.html: src=../contact/{h}/bandwidth-6m.svg
example.org/index.html: src=../contact/{h}/uptime-1m.svg
relay/{A}/bandwidth-1m.svg
relay/{A}/bandwidth-6m.svg
relay/{A}/index.html: href=bandwidth-1m.svg
relay/{A}/index.html: href=bandwidth-6m.svg
relay/{A}/index.html: href=uptime-1m.svg
relay/{A}/index.html: src=bandwidth-1m.svg
relay/{A}/index.html: src=bandwidth-1m.svg
relay/{A}/index.html: src=bandwidth-6m.svg
relay/{A}/index.html: src=bandwidth-6m.svg
relay/{A}/index.html: src=uptime-1m.svg
relay/{A}/uptime-1m.svg
relay/{B}/bandwidth-1m.svg
relay/{B}/index.html: href=bandwidth-1m.svg
relay/{B}/index.html: src=bandwidth-1m.svg
relay/{C}/bandwidth-1m.svg
relay/{C}/index.html: href=bandwidth-1m.svg
relay/{C}/index.html: src=bandwidth-1m.svg
"""


class _Clock(object):
    """time_utils' ``datetime``, with ``now()`` at NOW."""

    @staticmethod
    def now(tz):
        return NOW.astimezone(tz)

    def __getattr__(self, name):
        return getattr(datetime, name)


@pytest.fixture
def frozen_clock(monkeypatch):
    """Stop the clocks the pages read ("Last updated", "UP 2w 6d 4h ago"), so a build is the same on any day."""
    monkeypatch.setattr(time, "time", NOW.timestamp)
    monkeypatch.setattr(time_utils, "datetime", _Clock())


def _relay(fingerprint):
    return {
        "nickname": "relay" + fingerprint[0], "fingerprint": fingerprint, "running": True,
        "observed_bandwidth": 1_000_000, "advertised_bandwidth": 1_000_000, "consensus_weight": 100,
        "flags": ["Guard", "Running", "Valid"], "first_seen": "2024-01-01 00:00:00", "last_seen": PUBLISHED,
        "last_restarted": "2026-09-10 08:00:00", "platform": "Tor 0.4.8.10 on Linux", "country": "de",
        "country_name": "Germany", "as": "AS100", "as_name": "Example Networks", "or_addresses": ["192.0.2.1:9001"],
        "contact": "operator@" + DOMAIN, "effective_family": [fingerprint],
    }


def _build(out, layout, monkeypatch):
    """Write the contact (with its vanity copy) and relay pages, and their charts, as allium.py does in ``layout``.
    Returns the contact's hash."""
    relay_set = Relays(output_dir=str(out), onionoo_url="https://onionoo.example.invalid/details",
                       relay_data={"version": "8.0", "relays_published": PUBLISHED, "relays": [_relay(fp) for fp in FPS]},
                       filter_downtime_days=0, mp_workers=0, base_url="https://metrics.example.org")
    relay_set.enrich_with_api_data()
    (contact_hash, contact_data), = relay_set.json["sorted"]["contact"].items()
    contact_data.update(is_validated_aroi=True, aroi_domain=DOMAIN)
    # Every relay has a 1M bandwidth history, the first also a 6M one (so its charts get thumbnails) and an uptime one.
    bandwidth = {fp: history([100] * 30) for fp in FPS}
    for direction, block in history([100] * 180, key="6_months", first="2026-04-03 12:00:00").items():
        bandwidth[FPS[0]][direction].update(block)
    relay_set.chart_writer = writer(relay_set.json["relays"], bandwidth,
                                    {FPS[0]: [999] * 180}, root=str(out / CHARTS_DIR) if layout == "charts" else None)
    monkeypatch.setitem(page_writer.ENV.globals, "chart_root", CHARTS_DIR + "/" if layout == "charts" else "")
    clear_chart_tree(str(out))
    page_writer.write_pages_by_key(relay_set, "contact")
    page_writer.write_relay_info(relay_set)
    return contact_hash


def _charts_written(out):
    return {os.path.relpath(os.path.join(folder, name), out)
            for folder, _dirs, names in os.walk(out) for name in names if CHART.fullmatch(name)}


def _charts_referenced(out):
    """{page: [chart paths its src and href attributes resolve to, from the output root]} for every page."""
    pages = {}
    for folder, _dirs, names in os.walk(out):
        for name in names:
            if name.endswith(".html"):
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    refs = CHART_REF.findall(handle.read())
                pages[os.path.relpath(os.path.join(folder, name), out)] = [
                    os.path.relpath(os.path.normpath(os.path.join(folder, ref)), out) for ref in refs]
    return pages


def _chart_links(out, contact):
    """BESIDE's text for a build: every file but the pages, and a "<page>: <attribute>=<link>" line for each chart
    link on the relay pages, the contact page and its vanity-domain copy, sorted."""
    lines = []
    for folder, _dirs, names in os.walk(out):
        for name in names:
            page = os.path.relpath(os.path.join(folder, name), out).replace(os.sep, "/")
            if not name.endswith(".html"):
                lines.append(page)
            elif name == "index.html" and page.split("/")[0] in ("relay", "contact", DOMAIN):
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    lines += ["%s: %s=%s" % (page, attribute, link) for attribute, link in LINK.findall(handle.read())
                              if CHART.fullmatch(link.rsplit("/", 1)[-1])]
    text = "".join(line + "\n" for line in sorted(lines))
    for letter, fingerprint in zip("ABC", FPS):
        text = text.replace(fingerprint, "{%s}" % letter)
    return text.replace(contact, "{h}")


@pytest.mark.parametrize("layouts", [("beside", "charts", "beside"), ("charts", "beside")])
def test_pages_reference_exactly_the_charts_of_their_layout(tmp_path, monkeypatch, frozen_clock, layouts):
    """Each build writes its charts in its own layout, leaves none of an earlier build's other layout behind, and
    every chart reference on a relay, contact or vanity-domain page is relative and resolves to a chart written; the
    contact page's sort variants link the same charts. A beside build, first or after a charts build, writes the files
    and chart links master did."""
    out = tmp_path / "www"
    for layout in layouts:
        contact = _build(out, layout, monkeypatch)
        apart = CHARTS_DIR + "/" if layout == "charts" else ""
        expected = {"%srelay/%s/bandwidth-1m.svg" % (apart, fp) for fp in FPS}
        expected |= {"%srelay/%s/%s.svg" % (apart, FPS[0], name) for name in ("uptime-1m", "bandwidth-6m")}
        expected |= {"%scontact/%s/bandwidth-%s.svg" % (apart, contact, period) for period in ("1m", "6m")}
        expected.add("%scontact/%s/uptime-1m.svg" % (apart, contact))
        assert _charts_written(out) == {path.replace("/", os.sep) for path in expected}, layout
        assert (out / CHARTS_DIR).exists() is (layout == "charts")

        pages = _charts_referenced(out)
        assert set(path for refs in pages.values() for path in refs) == set(_charts_written(out))
        relay_page, contact_page, vanity_page = (os.path.join("relay", FPS[0], "index.html"),
                                                 os.path.join("contact", contact, "index.html"),
                                                 os.path.join(DOMAIN, "index.html"))
        assert pages[relay_page] and pages[contact_page] and pages[vanity_page]
        for index in (contact_page, vanity_page):
            variants = [page for page in pages if os.path.dirname(page) == os.path.dirname(index) and page != index]
            assert variants and all(sorted(pages[page]) == sorted(pages[index]) for page in variants), index
        relay_html, contact_html, vanity_html = ((out / page).read_text() for page in (relay_page, contact_page, vanity_page))
        if layout == "beside":  # as before --chart-layout
            assert _chart_links(out, contact) == BESIDE
            assert 'href="bandwidth-1m.svg"><img src="bandwidth-1m.svg"' in relay_html
            assert 'src="uptime-1m.svg"' in relay_html
            assert 'src="../../contact/%s/bandwidth-1m.svg"' % contact in contact_html
            assert 'src="../../contact/%s/uptime-1m.svg"' % contact in contact_html
            assert 'src="../contact/%s/bandwidth-1m.svg"' % contact in vanity_html
            assert 'src="../contact/%s/uptime-1m.svg"' % contact in vanity_html
        else:  # relative to the page, so the site still works from a subdirectory or file://
            chart = "../../charts/relay/%s/bandwidth-1m.svg" % FPS[0]
            assert 'href="%s"><img src="%s"' % (chart, chart) in relay_html
            assert 'src="../../charts/relay/%s/uptime-1m.svg"' % FPS[0] in relay_html
            assert 'src="../../charts/contact/%s/bandwidth-1m.svg"' % contact in contact_html
            assert 'src="../../charts/contact/%s/uptime-1m.svg"' % contact in contact_html
            assert 'src="../charts/contact/%s/bandwidth-1m.svg"' % contact in vanity_html
            assert 'src="../charts/contact/%s/uptime-1m.svg"' % contact in vanity_html
