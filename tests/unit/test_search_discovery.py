"""Tests for robots.txt and sitemap generation."""

import os
from xml.etree import ElementTree as ET

import pytest

from allium.lib.search_discovery import (
    SITEMAP_NAMESPACE,
    _route_for_html,
    generate_search_discovery,
)


def test_route_for_html_uses_public_canonical_forms():
    assert _route_for_html("index.html") == "/"
    assert _route_for_html("relay/ABC/index.html") == "/relay/ABC/"
    assert _route_for_html("misc/all.html") == "/misc/all"
    assert _route_for_html("404.html") is None


def test_generates_exact_robots_and_valid_sitemap(temp_dir):
    os.makedirs(os.path.join(temp_dir, "relay", "ABC"))
    for relative in ("index.html", "top500.html", "relay/ABC/index.html", "404.html"):
        destination = os.path.join(temp_dir, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, "w", encoding="utf-8") as handle:
            handle.write("<!doctype html><title>public</title>")

    stats = generate_search_discovery(temp_dir, "https://metrics.1aeo.com/")

    assert stats == {"generated": True, "url_count": 3, "sitemap_count": 1}
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


def test_local_build_skips_public_discovery_files(temp_dir):
    for filename in ("robots.txt", "sitemap.xml", "sitemap-1.xml"):
        with open(os.path.join(temp_dir, filename), "w", encoding="utf-8") as handle:
            handle.write("stale production content")

    assert generate_search_discovery(temp_dir, "") == {
        "generated": False,
        "url_count": 0,
        "sitemap_count": 0,
    }
    assert not os.path.exists(os.path.join(temp_dir, "robots.txt"))
    assert not os.path.exists(os.path.join(temp_dir, "sitemap.xml"))
    assert not os.path.exists(os.path.join(temp_dir, "sitemap-1.xml"))


@pytest.mark.parametrize(
    "base_url",
    [
        "http://metrics.1aeo.com",
        "https://user:pass@metrics.1aeo.com",
        "https://metrics.1aeo.com/private",
        "https://metrics.1aeo.com?preview=1",
    ],
)
def test_non_public_base_urls_are_rejected_or_skipped(temp_dir, base_url):
    if base_url.startswith("http://"):
        assert generate_search_discovery(temp_dir, base_url)["generated"] is False
    else:
        with pytest.raises(ValueError):
            generate_search_discovery(temp_dir, base_url)
