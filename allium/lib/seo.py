"""SEO URL helpers and crawler discovery files for generated sites."""

from concurrent.futures import ProcessPoolExecutor
import functools
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
# Every spelling _HREF_RE accepts for "href" (its letters have no non-ASCII
# case-insensitive equivalents).
_HREF_SPELLINGS = frozenset(
    h + r + e + f for h in "hH" for r in "rR" for e in "eE" for f in "fF"
)
# ".html" split by tab/CR/LF, which urlsplit strips before checking the path
_SPLIT_HTML_RE = re.compile(
    r"\.(?:[\t\r\n]+h[\t\r\n]*t[\t\r\n]*m[\t\r\n]*l"
    r"|h(?:[\t\r\n]+t[\t\r\n]*m[\t\r\n]*l|t(?:[\t\r\n]+m[\t\r\n]*l|m[\t\r\n]+l)))"
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


def canonical_url_for_output(base_url, relative_path):
    """Return an absolute canonical when possible, otherwise root-relative."""
    route = route_for_html(canonical_output_path(relative_path))
    if route is None:
        return None
    base = public_base_url(base_url)
    return f"{base}{route}" if base else route


def clean_href(path):
    """Convert a relative generated HTML link to its clean-route equivalent."""
    if not path or not path.endswith(".html"):
        return path
    if path.endswith("/index.html"):
        return path[:-10]
    if path == "index.html":
        return "./"
    return path[:-5]


@functools.lru_cache(maxsize=1 << 17)
def _clean_route_href(value):
    """Return the clean-route form of an internal ``.html`` href, else ``None``.

    Cached because the same links (navigation, relay/AS/country links) repeat
    across thousands of generated pages.
    """
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or value.startswith(("#", "//")):
        return None
    if not parsed.path.endswith(".html"):
        return None
    return urlunsplit(
        ("", "", clean_href(parsed.path), parsed.query, parsed.fragment)
    )


def _href_attr_start(html, quote_at):
    """Return where ``\\bhref\\s*=\\s*`` ends right before ``html[quote_at]``, else -1.

    Mirrors the prefix of ``_HREF_RE`` backwards (``\\s`` and ``\\b`` follow
    ``str.isspace`` and ``str.isalnum``, as the regex engine does).
    """
    end = quote_at
    while end > 0 and html[end - 1].isspace():
        end -= 1
    if end == 0 or html[end - 1] != "=":
        return -1
    end -= 1
    while end > 0 and html[end - 1].isspace():
        end -= 1
    start = end - 4
    if start < 0 or html[start:end] not in _HREF_SPELLINGS:
        return -1
    if start > 0 and (html[start - 1].isalnum() or html[start - 1] == "_"):
        return -1
    return start


def _last_quote_before(html, index):
    # Bound the search for the (rare) single quote by the nearest double quote
    double = html.rfind('"', 0, index)
    return max(double, html.rfind("'", max(double, 0), index))


def _first_quote_from(html, index):
    double = html.find('"', index)
    single = html.find("'", index, double if double >= 0 else len(html))
    return single if single >= 0 else double


def _internal_html_href_spans(html):
    """Return the ``(start, quote_at, end)`` spans ``_HREF_RE`` would match
    whose value contains ``.html``, or ``None`` when a value could swallow a
    following attribute and only a full scan is exact.

    A match's value holds no quotes, so the match covering a ``.html`` must
    open at the last quote before it and close at the first one after it.
    Pages carry few ``.html`` links but thousands of other hrefs, so this
    skips the per-href work of a full scan.
    """
    spans = []
    index = html.find(".html")
    while index >= 0:
        next_index = index + 5
        quote_at = _last_quote_before(html, index)
        if quote_at >= 0:
            quote_char = html[quote_at]
            close_at = _first_quote_from(html, index)
            start = (_href_attr_start(html, quote_at)
                     if close_at >= 0 and html[close_at] == quote_char else -1)
            if start >= 0:
                # A value ending in "href=" would make the regex consume this
                # attribute's opening quote as its closing one.
                earlier_quote = _last_quote_before(html, start)
                if (earlier_quote >= 0 and html[earlier_quote] == quote_char
                        and _href_attr_start(html, earlier_quote) >= 0):
                    return None
                if not spans or spans[-1][0] != start:
                    spans.append((start, quote_at, close_at + 1))
                next_index = close_at + 1
        index = html.find(".html", next_index)
    return spans


def _rewrite_internal_links_full_scan(html):
    changed_links = 0

    def replacement(match):
        nonlocal changed_links
        rewritten = _clean_route_href(match.group("value"))
        if rewritten is None:
            return match.group(0)
        changed_links += 1
        quote_char = match.group("quote")
        return f"{match.group('prefix')}{quote_char}{rewritten}{quote_char}"

    return _HREF_RE.sub(replacement, html), changed_links


def rewrite_internal_links(html):
    """Return ``(html, changed_links)`` with internal ``.html`` hrefs in clean-route form."""
    spans = (None if _SPLIT_HTML_RE.search(html)
             else _internal_html_href_spans(html))
    if spans is None:
        return _rewrite_internal_links_full_scan(html)
    parts = []
    changed_links = 0
    position = 0
    for start, quote_at, end in spans:
        rewritten = _clean_route_href(html[quote_at + 1:end - 1])
        if rewritten is None:
            continue
        quote_char = html[quote_at]
        parts.append(html[position:quote_at + 1])
        parts.append(rewritten)
        parts.append(quote_char)
        position = end
        changed_links += 1
    if not changed_links:
        return html, 0
    parts.append(html[position:])
    return "".join(parts), changed_links


def _rewrite_html_file(html_path):
    """Rewrite one HTML file and return changed-file and changed-link counts."""
    path = Path(html_path)
    original = path.read_text(encoding="utf-8")
    rewritten, changed_links = rewrite_internal_links(original)
    if rewritten == original:
        return 0, changed_links
    path.write_text(rewritten, encoding="utf-8")
    return 1, changed_links


def rewrite_internal_html_links(output_dir, modified_before=None):
    """Rewrite internal ``.html`` hrefs to their public clean-route forms.

    ``modified_before`` (a POSIX timestamp) limits the pass to files last
    written before it. Pages rendered by the current run are already
    rewritten as they are written, so only older leftovers need a pass.
    """
    output_path = Path(output_dir)
    html_paths = [
        str(path)
        for path in sorted(output_path.rglob("*.html"))
        if path.is_file()
        and (modified_before is None or path.stat().st_mtime < modified_before)
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
