"""Tests for robots.txt and sitemap generation."""

import os
from xml.etree import ElementTree as ET

import pytest

from allium.lib.search_discovery import (
    SITEMAP_NAMESPACE,
    _pack_sitemap_urls,
    _route_for_html,
    _serialize_xml,
    _urlset,
    generate_search_discovery,
)


def test_route_for_html_uses_public_canonical_forms():
    assert _route_for_html("index.html") == "/"
    assert _route_for_html("relay/ABC/index.html") == "/relay/ABC/"
    assert _route_for_html("misc/all.html") == "/misc/all"
    assert _route_for_html("404.html") is None


def test_generates_exact_robots_and_valid_sitemap(temp_dir):
    os.makedirs(os.path.join(temp_dir, "relay", "ABC"))
    canonicals = {
        "index.html": "https://metrics.1aeo.com/",
        "top500.html": "https://metrics.1aeo.com/top500",
        "relay/ABC/index.html": "https://metrics.1aeo.com/relay/ABC/",
    }
    for relative in (*canonicals, "404.html"):
        destination = os.path.join(temp_dir, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, "w", encoding="utf-8") as handle:
            canonical = canonicals.get(relative, "")
            handle.write(
                "<!doctype html><html><head><title>public</title>"
                f'<link rel="canonical" href="{canonical}">'
                "</head><body></body></html>"
            )

    stats = generate_search_discovery(temp_dir, "https://metrics.1aeo.com/")

    assert stats == {
        "generated": True,
        "url_count": 3,
        "sitemap_count": 1,
        "html_count": 3,
        "noindex_count": 0,
    }
    with open(os.path.join(temp_dir, "robots.txt"), encoding="utf-8") as handle:
        assert handle.read() == (
            "User-agent: *\n"
            "Allow: /\n"
            "Sitemap: https://metrics.1aeo.com/sitemap.xml\n"
        )

    root = ET.parse(os.path.join(temp_dir, "sitemap.xml")).getroot()
    assert root.tag == f"{{{SITEMAP_NAMESPACE}}}urlset"
    locations = [
        node.text for node in root.findall(f"{{{SITEMAP_NAMESPACE}}}url/{{{SITEMAP_NAMESPACE}}}loc")
    ]
    assert locations == [
        "https://metrics.1aeo.com/",
        "https://metrics.1aeo.com/relay/ABC/",
        "https://metrics.1aeo.com/top500",
    ]


def test_generates_discovery_for_prefixed_public_base_url(temp_dir):
    destination = os.path.join(temp_dir, "index.html")
    with open(destination, "w", encoding="utf-8") as handle:
        handle.write(
            "<!doctype html><html><head>"
            '<link rel="canonical" '
            'href="https://example.com/tor-metrics/">'
            "</head><body></body></html>"
        )

    stats = generate_search_discovery(
        temp_dir, "https://example.com/tor-metrics/"
    )

    assert stats["url_count"] == 1
    with open(os.path.join(temp_dir, "robots.txt"), encoding="utf-8") as handle:
        assert handle.read() == (
            "User-agent: *\n"
            "Allow: /\n"
            "Sitemap: https://example.com/tor-metrics/sitemap.xml\n"
        )
    root = ET.parse(os.path.join(temp_dir, "sitemap.xml")).getroot()
    location = root.find(
        f"{{{SITEMAP_NAMESPACE}}}url/{{{SITEMAP_NAMESPACE}}}loc"
    )
    assert location.text == "https://example.com/tor-metrics/"


def test_noindex_is_preserved_across_multiple_robots_tags(temp_dir):
    pages = {
        "index.html": (
            '<meta name="robots" content="noindex, follow">'
            '<meta name="robots" content="index, follow">'
            '<link rel="canonical" href="https://metrics.1aeo.com/">'
        ),
        "top500.html": (
            '<link rel="canonical" href="https://metrics.1aeo.com/top500">'
        ),
    }
    for relative, head in pages.items():
        destination = os.path.join(temp_dir, relative)
        with open(destination, "w", encoding="utf-8") as handle:
            handle.write(
                f"<!doctype html><html><head>{head}</head><body></body></html>"
            )

    stats = generate_search_discovery(temp_dir, "https://metrics.1aeo.com")

    assert stats["noindex_count"] == 1
    assert stats["url_count"] == 1
    root = ET.parse(os.path.join(temp_dir, "sitemap.xml")).getroot()
    locations = [
        node.text
        for node in root.findall(
            f"{{{SITEMAP_NAMESPACE}}}url/{{{SITEMAP_NAMESPACE}}}loc"
        )
    ]
    assert locations == ["https://metrics.1aeo.com/top500"]


def test_local_build_skips_public_discovery_files(temp_dir):
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


def test_long_nested_routes_are_sharded_before_byte_limit():
    urls = [
        "https://metrics.1aeo.com/" + "nested-route/" * 20 + str(index)
        for index in range(6)
    ]
    two_url_size = len(_serialize_xml(_urlset(urls[:2])))

    groups = _pack_sitemap_urls(urls, max_urls=50_000, max_bytes=two_url_size)

    assert len(groups) == 3
    assert [len(group) for group in groups] == [2, 2, 2]
    assert all(
        len(_serialize_xml(_urlset(group))) <= two_url_size
        for group in groups
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://metrics.1aeo.com",
        "https://user:pass@metrics.1aeo.com",
        "https://metrics.1aeo.com?preview=1",
    ],
)
def test_non_public_base_urls_are_rejected_or_skipped(temp_dir, base_url):
    if base_url.startswith("http://"):
        assert generate_search_discovery(temp_dir, base_url)["generated"] is False
    else:
        with pytest.raises(ValueError):
            generate_search_discovery(temp_dir, base_url)
