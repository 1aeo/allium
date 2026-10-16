"""Tests for canonical URLs, clean links, and crawler discovery files."""

import multiprocessing
import os
import random
import re
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree as ET

from jinja2 import Environment, FileSystemLoader, select_autoescape
import pytest

from allium.lib import seo
from allium.lib.search_discovery import (
    SITEMAP_NAMESPACE,
    generate_search_discovery,
)
from allium.lib.seo import (
    canonical_output_path,
    canonical_url_for_output,
    clean_href,
    oversized_html_files,
    public_base_url,
    rewrite_internal_html_links,
    rewrite_internal_links,
    root_relative_base_prefix,
    route_for_html,
)


def _write_page(root, relative, canonical, robots=None, body=""):
    destination = os.path.join(root, relative)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    robots_meta = (
        f'<meta name="robots" content="{robots}">' if robots else ""
    )
    with open(destination, "w", encoding="utf-8") as handle:
        handle.write(
            "<!doctype html><html><head>"
            f'<link rel="canonical" href="{canonical}">{robots_meta}'
            f"</head><body>{body}</body></html>"
        )


@pytest.mark.parametrize(
    ("relative,expected"),
    [
        ("index.html", "/"),
        ("top500.html", "/top500"),
        ("relay/ABC/index.html", "/relay/ABC/"),
        ("misc/all-page-2.html", "/misc/all-page-2"),
    ],
)
def test_route_for_html_uses_clean_public_routes(relative, expected):
    assert route_for_html(relative) == expected


def test_canonical_duplicate_mapping_preserves_pagination_page():
    assert canonical_output_path(
        "misc/contacts-by-consensus-weight.html"
    ) == "misc/contacts-by-bandwidth.html"
    assert canonical_output_path(
        "misc/contacts-by-consensus-weight-page-3.html"
    ) == "misc/contacts-by-bandwidth-page-3.html"
    assert canonical_output_path("misc/aroi-leaderboards.html") == "index.html"


def test_canonical_url_is_absolute_or_root_relative():
    assert canonical_url_for_output(
        "https://metrics.1aeo.com/", "country/US/index.html"
    ) == "https://metrics.1aeo.com/country/US/"
    assert canonical_url_for_output(
        "", "country/US/index.html"
    ) == "/country/US/"
    assert public_base_url("https://example.test/metrics/") == (
        "https://example.test/metrics"
    )


def test_canonical_url_preserves_root_relative_subdirectory_prefix():
    """Documented --base-url /tor-metrics must prefix every canonical route.

    The route shape from route_for_html is preserved; only the prefix is
    added. skeleton.html uses the same canonical_url for og:url.
    """
    assert canonical_url_for_output(
        "/tor-metrics", "index.html"
    ) == "/tor-metrics/"
    assert canonical_url_for_output(
        "/tor-metrics/", "index.html"
    ) == "/tor-metrics/"
    assert canonical_url_for_output(
        "/tor-metrics/", "country/US/index.html"
    ) == "/tor-metrics/country/US/"
    assert canonical_url_for_output(
        "/tor-metrics", "country/US.html"
    ) == "/tor-metrics/country/US"
    assert canonical_url_for_output(
        "/tor-metrics", "misc/all-page-2.html"
    ) == "/tor-metrics/misc/all-page-2"
    assert canonical_url_for_output(
        "/tor-metrics", "example.org/page-2.html"
    ) == "/tor-metrics/example.org/page-2"
    assert canonical_url_for_output(
        "/tor-metrics", "misc/contacts-by-consensus-weight.html"
    ) == "/tor-metrics/misc/contacts-by-bandwidth"
    assert canonical_url_for_output("/tor-metrics", "404.html") is None
    assert root_relative_base_prefix("/tor-metrics/") == "/tor-metrics"


def test_absolute_base_with_path_stays_on_public_base_url():
    """http(s) bases, including a path prefix, are unchanged."""
    assert canonical_url_for_output(
        "https://example.com/tor-metrics", "country/US/index.html"
    ) == "https://example.com/tor-metrics/country/US/"
    assert canonical_url_for_output(
        "https://example.com/tor-metrics/", "index.html"
    ) == "https://example.com/tor-metrics/"
    assert canonical_url_for_output(
        "http://example.com/tor-metrics", "misc/all-page-2.html"
    ) == "http://example.com/tor-metrics/misc/all-page-2"
    assert public_base_url("https://example.com/tor-metrics/") == (
        "https://example.com/tor-metrics"
    )
    assert root_relative_base_prefix("https://example.com/tor-metrics") is None


def test_unsafe_root_relative_bases_are_not_canonical_prefixes():
    """Bare '/', scheme-relative, and browser-normalized equivalents stay out.

    The CLI rejects these before generation. Canonical construction must not
    turn the ones browsers collapse into '//' into an off-site href.
    """
    assert root_relative_base_prefix("/") is None
    assert root_relative_base_prefix("") is None
    assert root_relative_base_prefix(None) is None
    assert canonical_url_for_output("/", "country/US/index.html") == "/country/US/"
    assert canonical_url_for_output(
        "//evil.example/tor-metrics", "index.html"
    ) == "/"
    for base_url in (
        "/",
        "/ ",
        " /",
        "\t/\n",
        "\\",
        "/\\",
        "/\t/evil.example",
        "/\n/evil.example",
        "/\r/evil.example",
        "//evil.example/path",
        "///tor-metrics",
        "/tor-metrics?preview=1",
        "/tor-metrics#frag",
    ):
        prefix = root_relative_base_prefix(base_url)
        assert prefix is None, base_url
        canonical = canonical_url_for_output(base_url, "country/US/index.html")
        assert canonical == "/country/US/", base_url
        assert not canonical.startswith("//")


def test_subdirectory_canonical_is_also_the_og_url():
    """og:url reuses canonical_url; relative page links stay path-relative."""
    canonical = canonical_url_for_output("/tor-metrics", "country/US/index.html")
    template_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "allium", "templates"
    )
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html"]),
    )
    template = env.from_string(
        '{% extends "skeleton.html" %}'
        "{% block title %}United States{% endblock %}"
        "{% block body %}<p>US</p>{% endblock %}"
    )
    html = template.render(
        canonical_url=canonical,
        page_ctx=SimpleNamespace(path_prefix="../../"),
        relays=SimpleNamespace(timestamp="2026-01-01"),
    )
    assert '<link rel="canonical" href="/tor-metrics/country/US/">' in html
    assert '<meta property="og:url" content="/tor-metrics/country/US/">' in html
    assert 'href="../../static/favicon.ico"' in html
    assert "/tor-metrics/static/" not in html


def test_link_rewrite_does_not_inject_subdirectory_prefix():
    """Internal links are relative to the generated tree, not the public prefix."""
    html = (
        '<a href="country/US/index.html">US</a>'
        '<a href="/misc/all.html">All</a>'
    )
    rewritten, changed = rewrite_internal_links(html)
    assert changed == 2
    assert rewritten == (
        '<a href="country/US/">US</a>'
        '<a href="/misc/all">All</a>'
    )


def test_public_base_rejects_unstable_components():
    with pytest.raises(ValueError):
        public_base_url("https://user:pass@example.test/")
    with pytest.raises(ValueError):
        public_base_url("https://example.test/?preview=1")


@pytest.mark.parametrize("min_files", [1, 256], ids=["pool", "in_process"])
def test_rewrites_only_internal_html_links(temp_dir, monkeypatch, min_files):
    monkeypatch.setattr(seo, "_PARALLEL_MIN_FILES", min_files)
    _write_page(
        temp_dir,
        "index.html",
        "https://metrics.1aeo.com/",
        body=(
            '<a href="misc/all.html#relay-table">All</a>'
            '<a href="relay/ABC/index.html">Relay</a>'
            '<a href="https://spec.torproject.org/example.html">Spec</a>'
        ),
    )

    stats = rewrite_internal_html_links(temp_dir)

    assert stats == {"changed_files": 1, "changed_links": 2}
    rendered = open(os.path.join(temp_dir, "index.html"), encoding="utf-8").read()
    assert 'href="misc/all#relay-table"' in rendered
    assert 'href="relay/ABC/"' in rendered
    assert 'href="https://spec.torproject.org/example.html"' in rendered


def test_rewrite_skips_files_written_since_cutoff(temp_dir):
    _write_page(temp_dir, "old.html", "/", body='<a href="a/index.html">A</a>')
    _write_page(temp_dir, "new.html", "/", body='<a href="b/index.html">B</a>')
    old_path = os.path.join(temp_dir, "old.html")
    os.utime(old_path, (1_000_000, 1_000_000))

    stats = rewrite_internal_html_links(temp_dir, modified_before=2_000_000)

    assert stats == {"changed_files": 1, "changed_links": 1}
    assert 'href="a/"' in open(old_path, encoding="utf-8").read()
    new_page = open(os.path.join(temp_dir, "new.html"), encoding="utf-8").read()
    assert 'href="b/index.html"' in new_page


_REFERENCE_HREF_RE = re.compile(
    r"(?P<prefix>\bhref\s*=\s*)(?P<quote>[\"'])(?P<value>[^\"']+)(?P=quote)",
    re.IGNORECASE,
)


def _reference_rewrite(html):
    """The original whole-page regex rewrite that rewrite_internal_links replaced."""
    changed = 0

    def replacement(match):
        nonlocal changed
        value = match.group("value")
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or value.startswith(("#", "//")):
            return match.group(0)
        if not parsed.path.endswith(".html"):
            return match.group(0)
        changed += 1
        rewritten = urlunsplit(
            ("", "", clean_href(parsed.path), parsed.query, parsed.fragment))
        quote_char = match.group("quote")
        return f"{match.group('prefix')}{quote_char}{rewritten}{quote_char}"

    return _REFERENCE_HREF_RE.sub(replacement, html), changed


@pytest.mark.parametrize("html", [
    '<a href="misc/all.html#t">x</a> <a href="https://a.test/b.html">y</a>',
    "<a HREF='../relay/A/index.html?x=1'>x</a><a Href = \"index.html\">i</a>",
    '<a href="/abs/page.html">x</a><a href="//cdn.test/x.html">y</a>',
    '<a href="mailto:a.html">m</a><a href="#frag.html">f</a>',
    'see index.html in text <img src="pic.html"> <a data-href="x.html">d</a>',
    # A value ending in "href=" swallows the next attribute's opening quote
    '<a title="href=" href="x.html">x</a><a href="y.html">y</a>',
    '<a title="a href = \'" href=\'x.html\'>x</a>',
    '<a href="a.html"href="b.html">ab</a><a href="">e</a><a href="c.html.html">c</a>',
    # urlsplit drops tab/CR/LF, so these values still end in ".html"
    '<a href="a.ht\tml">x</a>',
    "<a href='misc/all.\nhtml#t'>x</a>",
    '<a href="x.h\r\ntml?q=1">x</a> <a href="y.html">y</a>',
])
def test_rewrite_internal_links_matches_reference(html):
    assert rewrite_internal_links(html) == _reference_rewrite(html)


def test_rewrite_internal_links_matches_reference_on_random_markup():
    tokens = [
        "href", "HREF", "hRef", "ahref", "_href", "=", " = ", "\t", "\n", "\u2003",
        '"', "'", "a.html", "index.html", "../x/index.html", "#f", "//h/a.html",
        "http://h/a.html", "?q=1", ".html", "html", "<a ", ">", "x", "\u00e9", "_",
        ".", "ht", "ml", "\r",
        'title="href="', 'href="x.html"', "href='y.html'",
    ]
    rng = random.Random(1234)
    for _ in range(20_000):
        html = "".join(rng.choice(tokens) for _ in range(rng.randint(1, 30)))
        assert rewrite_internal_links(html) == _reference_rewrite(html), html


def test_discovery_uses_unique_canonicals_and_excludes_noindex(temp_dir):
    _write_page(temp_dir, "index.html", "https://metrics.1aeo.com/")
    _write_page(
        temp_dir,
        "misc/aroi-leaderboards.html",
        "https://metrics.1aeo.com/",
    )
    _write_page(
        temp_dir,
        "contact/HASH/index.html",
        "https://metrics.1aeo.com/example.org/",
    )
    _write_page(
        temp_dir,
        "example.org/index.html",
        "https://metrics.1aeo.com/example.org/",
    )
    _write_page(
        temp_dir,
        "misc/diagnostics.html",
        "https://metrics.1aeo.com/misc/diagnostics",
        robots="noindex,follow",
    )

    stats = generate_search_discovery(temp_dir, "https://metrics.1aeo.com")

    assert stats == {
        "generated": True,
        "url_count": 2,
        "sitemap_count": 1,
        "html_count": 5,
        "noindex_count": 1,
    }
    with open(os.path.join(temp_dir, "robots.txt"), encoding="utf-8") as handle:
        assert handle.read() == (
            "User-agent: *\n"
            "Allow: /\n"
            "Sitemap: https://metrics.1aeo.com/sitemap.xml\n"
        )
    root = ET.parse(os.path.join(temp_dir, "sitemap.xml")).getroot()
    locations = [
        node.text
        for node in root.findall(
            f"{{{SITEMAP_NAMESPACE}}}url/{{{SITEMAP_NAMESPACE}}}loc"
        )
    ]
    assert locations == [
        "https://metrics.1aeo.com/",
        "https://metrics.1aeo.com/example.org/",
    ]


def test_local_build_removes_public_discovery_files(temp_dir):
    for filename in ("robots.txt", "sitemap.xml", "sitemap-1.xml"):
        with open(os.path.join(temp_dir, filename), "w", encoding="utf-8") as handle:
            handle.write("stale production content")

    assert generate_search_discovery(temp_dir, "") == {
        "generated": False,
        "url_count": 0,
        "sitemap_count": 0,
        "html_count": 0,
        "noindex_count": 0,
    }
    assert not os.path.exists(os.path.join(temp_dir, "robots.txt"))
    assert not os.path.exists(os.path.join(temp_dir, "sitemap.xml"))
    assert not os.path.exists(os.path.join(temp_dir, "sitemap-1.xml"))


def test_size_guard_reports_only_oversized_html(temp_dir):
    _write_page(temp_dir, "small.html", "/small")
    _write_page(temp_dir, "large.html", "/large", body="x" * 500)
    assert oversized_html_files(temp_dir, max_bytes=300) == [
        ("large.html", os.path.getsize(os.path.join(temp_dir, "large.html")))
    ]


def _upper(path):
    """Dies like an OOM-killed worker on a poisoned path; raises on a bad one."""
    if path.endswith("poison") and multiprocessing.parent_process():
        os._exit(1)
    if path.endswith("bad"):
        raise ValueError(path)
    return path.upper()


def test_map_html_files_finishes_in_process_when_a_worker_dies(monkeypatch, caplog):
    monkeypatch.setattr(seo, "_PARALLEL_MIN_FILES", 2)
    paths = [f"p{i:02d}" for i in range(40)]
    paths[25] = "p25-poison"

    assert list(seo.map_html_files(_upper, paths, 4)) == [p.upper() for p in paths]
    assert "worker pool failed" in caplog.text
    paths[9], paths[30] = "p09-bad", "p30-bad"  # errors still raise in path order
    with pytest.raises(ValueError, match="p09-bad"):
        list(seo.map_html_files(_upper, paths, 4))
