"""Deterministic documentation-contract checks against code and CLI output."""

import os
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKIP_DIRS = {
    ".git",
    "venv",
    ".venv",
    "node_modules",
    "www",
    "htmlcov",
    ".pytest_cache",
    "build",
    "dist",
}


def _strip_code(text):
    """Remove fenced code blocks and inline code spans before parsing Markdown links."""
    stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    stripped = re.sub(r"~~~.*?~~~", "", stripped, flags=re.DOTALL)
    return re.sub(r"`[^`\n]+`", "", stripped)


def _iter_markdown_files():
    """Yield every Markdown file in the repository outside build/cache directories."""
    for root, dirs, files in os.walk(_REPO_ROOT):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        for name in sorted(files):
            if name.endswith(".md"):
                yield Path(root) / name


def test_cli_options_match_configuration_guide():
    """Every CLI flag in allium.py --help is documented in docs/user-guide/configuration.md (and vice versa)."""
    run = subprocess.run(
        [sys.executable, str(_REPO_ROOT / "allium" / "allium.py"), "--help"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=25,
        check=True,
    )
    cli_flags = set(re.findall(r"--[a-z][a-z0-9-]+", run.stdout)) - {"--help"}
    assert cli_flags, "expected CLI flags from allium.py --help"

    config_text = (_REPO_ROOT / "docs" / "user-guide" / "configuration.md").read_text(encoding="utf-8")
    section_match = re.search(
        r"^### All Options\n(.*?)(?=^### |\Z)",
        config_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert section_match, "missing '### All Options' section in docs/user-guide/configuration.md"

    doc_flags = set()
    progress_cell = ""
    for line in section_match.group(1).splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().split("|")]
        if len(cells) < 3:
            continue
        first_col = cells[1]
        flags = re.findall(r"--[a-z][a-z0-9-]+", first_col)
        doc_flags.update(flags)
        if "--progress" in flags:
            progress_cell = first_col

    assert doc_flags == cli_flags, (
        f"CLI flags mismatch in docs/user-guide/configuration.md: "
        f"missing={sorted(cli_flags - doc_flags)}, extra={sorted(doc_flags - cli_flags)}"
    )
    if re.search(r"(^|[\s,])\-p([,\s]|$)", run.stdout):
        assert re.search(r"\B-p\b", progress_cell), "short flag -p missing from --progress row"


def test_prometheus_metrics_documented():
    """Every emitted aeo1_* metric family in allium/lib/prometheus_metrics.py is documented in docs/prometheus/README.md."""
    metrics_src = (_REPO_ROOT / "allium" / "lib" / "prometheus_metrics.py").read_text(encoding="utf-8")
    emitted = set(re.findall(r'"(aeo1_[a-zA-Z0-9_]+)"', metrics_src))
    assert len(emitted) >= 20, f"expected >=20 emitted metrics, got {sorted(emitted)}"

    prom_readme = (_REPO_ROOT / "docs" / "prometheus" / "README.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"\baeo1_[a-zA-Z0-9_]+\b", prom_readme))
    missing = sorted(emitted - documented)
    assert not missing, f"undocumented emitted Prometheus metrics in docs/prometheus/README.md: {missing}"


def _is_escaped(text, index):
    """Return True when the character at index is preceded by an odd number of backslashes."""
    backslashes = 0
    pos = index - 1
    while pos >= 0 and text[pos] == "\\":
        backslashes += 1
        pos -= 1
    return (backslashes % 2) == 1


def _skip_optional_inline_title(text, pos, end):
    """Advance past optional inline link whitespace and '...', \"...\", or (...) title before ')'."""
    while pos < end and text[pos] in " \t\r\n":
        pos += 1
    if pos >= end or text[pos] == ")":
        return pos
    opener = text[pos]
    if opener not in ('"', "'", "("):
        return -1
    closer = ")" if opener == "(" else opener
    pos += 1
    while pos < end:
        ch = text[pos]
        if ch == "\\" and pos + 1 < end:
            pos += 2
            continue
        if opener == "(" and ch == "(":
            return -1
        if ch == closer:
            pos += 1
            while pos < end and text[pos] in " \t":
                pos += 1
            return pos
        pos += 1
    return -1


def _parse_inline_link(text, open_paren_pos):
    """Return (dest, end_pos) for an inline (...) link target or (None, open_paren_pos)."""
    n = len(text)
    pos = open_paren_pos + 1
    while pos < n and text[pos] in " \t":
        pos += 1
    if pos < n and text[pos] == "\r":
        pos += 1
    if pos < n and text[pos] == "\n":
        pos += 1
        while pos < n and text[pos] in " \t":
            pos += 1
    if pos >= n:
        return None, open_paren_pos

    if text[pos] == "<":
        pos += 1
        start = pos
        while pos < n and text[pos] not in (">", "\n"):
            if text[pos] == "\\" and pos + 1 < n:
                pos += 2
                continue
            pos += 1
        if pos >= n or text[pos] != ">":
            return None, open_paren_pos
        dest = text[start:pos].strip()
        pos += 1
    else:
        start = pos
        depth = 0
        while pos < n:
            ch = text[pos]
            if ch in (" ", "\t", "\r", "\n"):
                break
            if ch == "\\" and pos + 1 < n:
                pos += 2
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            pos += 1
        if depth != 0 or pos == start:
            return None, open_paren_pos
        dest = text[start:pos].strip()

    pos = _skip_optional_inline_title(text, pos, n)
    if pos < 0 or pos >= n or text[pos] != ")":
        return None, open_paren_pos
    return dest, pos + 1


def _parse_ref_definition(lines, idx):
    """Parse a CommonMark reference definition at lines[idx], returning (dest, next_idx) or (None, idx)."""
    m = re.match(r"^[ \t]{0,3}\[([^\]\n]+)\]:[ \t]*(.*)$", lines[idx])
    if not m or _is_escaped(lines[idx], lines[idx].index("[")):
        return None, idx

    cur = idx
    rest = m.group(2).strip()
    if not rest:
        if cur + 1 >= len(lines) or not lines[cur + 1].strip():
            return None, idx
        cur += 1
        rest = lines[cur].strip()

    if rest.startswith("<"):
        pos = 1
        while pos < len(rest) and rest[pos] != ">":
            if rest[pos] == "\\" and pos + 1 < len(rest):
                pos += 2
                continue
            pos += 1
        if pos >= len(rest):
            return None, idx
        dest = rest[1:pos].strip()
    else:
        dest = rest.split()[0] if rest else ""
    if not dest:
        return None, idx
    return dest, cur + 1


def _iter_link_targets(cleaned):
    """Yield destination strings from inline links and reference-style definitions."""
    idx = 0
    while idx < len(cleaned):
        close_idx = cleaned.find("](", idx)
        if close_idx == -1:
            break
        if _is_escaped(cleaned, close_idx):
            idx = close_idx + 2
            continue
        dest, end_pos = _parse_inline_link(cleaned, close_idx + 1)
        if dest is not None:
            if dest:
                yield dest
            idx = end_pos
        else:
            idx = close_idx + 2

    lines = cleaned.splitlines()
    line_idx = 0
    while line_idx < len(lines):
        dest, next_idx = _parse_ref_definition(lines, line_idx)
        if dest is not None:
            yield dest
            line_idx = next_idx
        else:
            line_idx += 1


def test_markdown_relative_links_resolve():
    """All relative links in repository Markdown files resolve to existing paths."""
    md_files = list(_iter_markdown_files())
    assert md_files, "expected Markdown files in repository"

    broken = []
    for md_path in md_files:
        cleaned = _strip_code(md_path.read_text(encoding="utf-8"))
        for target in _iter_link_targets(cleaned):
            if target.startswith(("#", "http://", "https://", "mailto:", "file://")):
                continue
            target_path = target.split("#", 1)[0].split("?", 1)[0]
            if not target_path:
                continue
            resolved = (md_path.parent / target_path).resolve()
            if not resolved.exists():
                broken.append(f"{md_path.relative_to(_REPO_ROOT)} -> {target}")

    assert not broken, "broken relative Markdown links:\n" + "\n".join(broken)
