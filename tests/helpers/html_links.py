"""Link checks over a generated site."""

import html
import re
from pathlib import Path

_FRAGMENT_HREF = re.compile(r'href="([^"#]*)#([^"]+)"')
_TARGET_ID = re.compile(r'\b(?:id|name)="([^"]*)"')
_EXTERNAL = ("http:", "https:", "//", "mailto:", "javascript:")


def dead_fragment_links(root, base_url=""):
    """(page, href) for each internal link whose #fragment names no element of the page it opens.

    "#x" must name an id on the page itself, "path#x" one on the generated page
    that path opens (a folder's index.html, or a clean route's .html file).
    Links under base_url count as root-relative. Links to pages that were not
    generated are left to the dead-link checks.
    """
    root = Path(root).resolve()
    ids = {}

    def ids_of(page):
        if page not in ids:
            ids[page] = {html.unescape(i) for i in _TARGET_ID.findall(page.read_text(encoding="utf-8"))}
        return ids[page]

    dead = []
    for page in sorted(root.rglob("*.html")):
        for target, fragment in sorted(set(_FRAGMENT_HREF.findall(page.read_text(encoding="utf-8")))):
            target = html.unescape(target).split("?", 1)[0]
            if base_url and target.startswith(base_url.rstrip("/") + "/"):
                target = target[len(base_url.rstrip("/")):]
            if target.lower().startswith(_EXTERNAL):
                continue
            opened = _opened_page(root, page, target)
            if opened and html.unescape(fragment) not in ids_of(opened):
                dead.append((page.relative_to(root).as_posix(), f"{target}#{fragment}"))
    return dead


def _opened_page(root, page, target):
    """The generated page a link opens, or None when it opens no generated page."""
    if not target:
        return page
    path = root / target.lstrip("/") if target.startswith("/") else page.parent / target
    if target.endswith("/") or path.is_dir():
        path = path / "index.html"
    elif not path.is_file():
        path = path.with_name(path.name + ".html")
    return path.resolve() if path.is_file() else None
