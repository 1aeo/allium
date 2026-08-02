"""Generate crawler discovery files for a completed static site build."""

from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
import xml.etree.ElementTree as ET


SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
MAX_URLS_PER_SITEMAP = 50_000
MAX_BYTES_PER_SITEMAP = 52_428_800

ET.register_namespace("", SITEMAP_NAMESPACE)


def _public_base_url(base_url):
    """Return a normalized public HTTPS origin, or ``None`` for local builds."""
    parsed = urlsplit(base_url or "")
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base_url must be a public HTTPS origin")
    if parsed.path not in ("", "/"):
        raise ValueError("base_url must not contain a path")
    return urlunsplit(("https", parsed.netloc, "", "", ""))


def _route_for_html(relative_path):
    """Map a generated HTML file to its extensionless canonical route."""
    relative_path = Path(relative_path)
    if relative_path.as_posix() == "404.html":
        return None
    if relative_path.name == "index.html":
        parent = relative_path.parent.as_posix()
        route = "/" if parent == "." else f"/{parent}/"
    else:
        route = f"/{relative_path.with_suffix('').as_posix()}"
    return quote(route, safe="/-._~")


def _generated_urls(output_dir, base_url):
    """Enumerate the real HTML routes present in the completed output tree."""
    output_path = Path(output_dir)
    urls = []
    for html_path in output_path.rglob("*.html"):
        if not html_path.is_file():
            continue
        route = _route_for_html(html_path.relative_to(output_path))
        if route is not None:
            urls.append(f"{base_url}{route}")
    return sorted(set(urls))


def _write_xml(root, destination):
    Path(destination).write_bytes(_serialize_xml(root))


def _serialize_xml(root):
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _urlset(urls):
    root = ET.Element(f"{{{SITEMAP_NAMESPACE}}}urlset")
    for url in urls:
        entry = ET.SubElement(root, f"{{{SITEMAP_NAMESPACE}}}url")
        ET.SubElement(entry, f"{{{SITEMAP_NAMESPACE}}}loc").text = url
    return root


def _pack_sitemap_urls(
        urls,
        max_urls=MAX_URLS_PER_SITEMAP,
        max_bytes=MAX_BYTES_PER_SITEMAP):
    """Pack URLs without exceeding either sitemap protocol limit."""
    sentinel = "x"
    one_entry_size = len(_serialize_xml(_urlset([sentinel])))
    added_entry_size = (
        len(_serialize_xml(_urlset([sentinel, sentinel]))) - one_entry_size
    )
    base_size = one_entry_size - added_entry_size
    groups = []
    current = []
    current_size = base_size

    for url in urls:
        entry_size = len(_serialize_xml(_urlset([url]))) - base_size
        if base_size + entry_size > max_bytes:
            raise ValueError(f"sitemap URL is too large to serialize: {url}")
        if current and (
                len(current) >= max_urls
                or current_size + entry_size > max_bytes):
            groups.append(current)
            current = []
            current_size = base_size
        current.append(url)
        current_size += entry_size

    if current:
        groups.append(current)
    return groups


def _remove_old_shards(output_path):
    for candidate in output_path.glob("sitemap-*.xml"):
        suffix = candidate.stem[len("sitemap-"):]
        if suffix.isdigit() and candidate.is_file():
            candidate.unlink()


def _remove_search_discovery(output_path) -> None:
    """Remove generated crawler files that are invalid for a local build."""
    for filename in ("robots.txt", "sitemap.xml"):
        candidate = output_path / filename
        if candidate.is_file():
            candidate.unlink()
    _remove_old_shards(output_path)


def generate_search_discovery(output_dir, base_url):
    """Write production robots and sitemap files.

    Local builds without an absolute HTTPS base URL are intentionally skipped,
    since sitemap ``loc`` values must be absolute public URLs.
    """
    output_path = Path(output_dir)
    public_base_url = _public_base_url(base_url)
    if public_base_url is None:
        _remove_search_discovery(output_path)
        return {"generated": False, "url_count": 0, "sitemap_count": 0}

    output_path.mkdir(parents=True, exist_ok=True)
    urls = _generated_urls(output_path, public_base_url)
    if not urls:
        raise ValueError("cannot generate a sitemap without public HTML routes")

    _remove_old_shards(output_path)
    sitemap_path = output_path / "sitemap.xml"
    url_groups = _pack_sitemap_urls(urls)
    if len(url_groups) == 1:
        _write_xml(_urlset(url_groups[0]), sitemap_path)
        sitemap_count = 1
    else:
        sitemap_count = 0
        sitemap_index = ET.Element(f"{{{SITEMAP_NAMESPACE}}}sitemapindex")
        for shard_urls in url_groups:
            sitemap_count += 1
            shard_name = f"sitemap-{sitemap_count}.xml"
            _write_xml(_urlset(shard_urls), output_path / shard_name)
            entry = ET.SubElement(
                sitemap_index, f"{{{SITEMAP_NAMESPACE}}}sitemap")
            ET.SubElement(
                entry, f"{{{SITEMAP_NAMESPACE}}}loc"
            ).text = f"{public_base_url}/{shard_name}"
        _write_xml(sitemap_index, sitemap_path)

    robots = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {public_base_url}/sitemap.xml\n"
    )
    (output_path / "robots.txt").write_text(robots, encoding="utf-8")
    return {
        "generated": True,
        "url_count": len(urls),
        "sitemap_count": sitemap_count,
    }
