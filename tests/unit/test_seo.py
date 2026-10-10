"""Tests for canonical URLs, clean links, and crawler discovery files."""

import os
import random
import re
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree as ET

import pytest

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


def test_public_base_rejects_unstable_components():
    with pytest.raises(ValueError):
        public_base_url("https://user:pass@example.test/")
    with pytest.raises(ValueError):
        public_base_url("https://example.test/?preview=1")


def test_rewrites_only_internal_html_links(temp_dir):
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
