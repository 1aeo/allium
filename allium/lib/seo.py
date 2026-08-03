"""SEO URL helpers and crawler discovery files for generated sites."""

from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote, urlsplit, urlunsplit


MAX_HTML_BYTES = 1_900_000

_MISC_SORT_RE = re.compile(
    r"^misc/(families|networks|contacts|countries|platforms)"
    r"-by-.+?(?P<page>-page-\d+)?\.html$"
)
_HREF_RE = re.compile(
    r"(?P<prefix>\bhref\s*=\s*)(?P<quote>[\"'])(?P<value>[^\"']+)(?P=quote)",
    re.IGNORECASE,
)


def public_base_url(base_url):
    """Return a normalized absolute HTTP(S) base URL, or ``None``.

    A path prefix is retained so Allium can still be hosted below an origin.
    Credentials, query strings, and fragments are rejected because they cannot
    form a stable public site base.
    """
    parsed = urlsplit(base_url or "")
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(
            "base_url must not contain credentials, a query string, or a fragment"
        )
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, path, "", ""))


def canonical_output_path(relative_path):
    """Map duplicate generated files to the one output path we canonicalize."""
    normalized = PurePosixPath(relative_path).as_posix().lstrip("/")
    if normalized == "misc/aroi-leaderboards.html":
        return "index.html"
    match = _MISC_SORT_RE.match(normalized)
    if match:
        page_suffix = match.group("page") or ""
        return f"misc/{match.group(1)}-by-bandwidth{page_suffix}.html"
    return normalized


def route_for_html(relative_path):
    """Map a generated HTML path to its clean public route."""
    relative = PurePosixPath(relative_path)
    if relative.as_posix().lstrip("/") == "404.html":
        return None
    if relative.suffix != ".html":
        raise ValueError(f"expected an HTML output path, got {relative_path!r}")
    if relative.name == "index.html":
        parent = relative.parent.as_posix().lstrip("/")
        route = "/" if parent in ("", ".") else f"/{parent}/"
    else:
        route = f"/{relative.with_suffix('').as_posix().lstrip('/')}"
    return quote(route, safe="/-._~")


def root_relative_base_prefix(base_url):
    """Return a normalized root-relative path prefix, or ``None``.

    Supports subdirectory previews such as ``/tor-metrics``. A bare ``/`` is
    rejected because templates build vanity links as ``{base}/{domain}/``, which
    would produce scheme-relative ``//{domain}/`` URLs.
    """
    if not base_url or not base_url.startswith("/") or base_url.startswith("//"):
        return None
    prefix = base_url.rstrip("/")
    if not prefix:
        raise ValueError(
            "base_url '/' is not supported; use a subdirectory prefix "
            "(e.g. '/tor-metrics') or an absolute http(s) URL"
        )
    return prefix


def canonical_url_for_output(base_url, relative_path):
    """Return an absolute canonical when possible, otherwise root-relative."""
    route = route_for_html(canonical_output_path(relative_path))
    if route is None:
        return None
    base = public_base_url(base_url)
    if base:
        return f"{base}{route}"
    prefix = root_relative_base_prefix(base_url)
    if prefix:
        return f"{prefix}{route}"
    return route


def clean_href(path):
    """Convert a relative generated HTML link to its clean-route equivalent."""
    if not path or not path.endswith(".html"):
        return path
    if path.endswith("/index.html"):
        return path[:-10]
    if path == "index.html":
        return "./"
    return path[:-5]


def _rewrite_html_file(html_path):
    """Rewrite one HTML file and return changed-file and changed-link counts."""
    changed_links = 0

    def replacement(match):
        nonlocal changed_links
        value = match.group("value")
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or value.startswith(("#", "//")):
            return match.group(0)
        if not parsed.path.endswith(".html"):
            return match.group(0)
        rewritten = urlunsplit(
            ("", "", clean_href(parsed.path), parsed.query, parsed.fragment)
        )
        changed_links += 1
        quote_char = match.group("quote")
        return f"{match.group('prefix')}{quote_char}{rewritten}{quote_char}"

    path = Path(html_path)
    original = path.read_text(encoding="utf-8")
    rewritten = _HREF_RE.sub(replacement, original)
    if rewritten == original:
        return 0, changed_links
    path.write_text(rewritten, encoding="utf-8")
    return 1, changed_links


def rewrite_internal_html_links(output_dir):
    """Rewrite internal ``.html`` hrefs to their public clean-route forms."""
    output_path = Path(output_dir)
    html_paths = [
        str(path)
        for path in sorted(output_path.rglob("*.html"))
        if path.is_file()
    ]
    if not html_paths:
        return {"changed_files": 0, "changed_links": 0}
    changed_files = changed_links = 0
    max_workers = min(8, os.cpu_count() or 1)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for file_count, link_count in executor.map(
                _rewrite_html_file, html_paths, chunksize=24):
            changed_files += file_count
            changed_links += link_count
    return {"changed_files": changed_files, "changed_links": changed_links}


def oversized_html_files(output_dir, max_bytes=MAX_HTML_BYTES):
    """Return generated HTML files that exceed the guarded crawl size."""
    output_path = Path(output_dir)
    return sorted(
        (
            (path.relative_to(output_path).as_posix(), path.stat().st_size)
            for path in output_path.rglob("*.html")
            if path.is_file() and path.stat().st_size > max_bytes
        ),
        key=lambda item: item[1],
        reverse=True,
    )
