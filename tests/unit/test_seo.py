"""Tests for canonical URLs, clean links, and crawler discovery files."""

import os
from xml.etree import ElementTree as ET

import pytest

from allium.lib.search_discovery import (
    SITEMAP_NAMESPACE,
    generate_search_discovery,
)
from allium.lib.seo import (
    canonical_output_path,
    canonical_url_for_output,
    oversized_html_files,
    public_base_url,
    rewrite_internal_html_links,
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
    """Documented --base-url /tor-metrics must prefix every canonical route."""
    assert canonical_url_for_output(
        "/tor-metrics", "index.html"
    ) == "/tor-metrics/"
    assert canonical_url_for_output(
        "/tor-metrics/", "country/US/index.html"
    ) == "/tor-metrics/country/US/"
    assert canonical_url_for_output(
        "/tor-metrics", "misc/all-page-2.html"
    ) == "/tor-metrics/misc/all-page-2"
    assert canonical_url_for_output(
        "/tor-metrics", "example.org/page-2.html"
    ) == "/tor-metrics/example.org/page-2"


def test_slash_only_base_url_is_rejected_for_canonicals():
    with pytest.raises(ValueError, match="not supported"):
        root_relative_base_prefix("/")
    with pytest.raises(ValueError, match="not supported"):
        canonical_url_for_output("/", "country/US/index.html")
    assert root_relative_base_prefix("/tor-metrics/") == "/tor-metrics"
    assert root_relative_base_prefix("") is None


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
