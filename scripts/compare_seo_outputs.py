#!/usr/bin/env python3
"""Compare pre/post SEO builds and reject changes outside the SEO contract."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urlunsplit


HEAD_RE = re.compile(r"<head\b[^>]*>.*?</head>", re.I | re.S)
HREF_RE = re.compile(
    r"(?P<prefix>\bhref\s*=\s*)(?P<quote>[\"'])(?P<value>[^\"']+)(?P=quote)",
    re.I,
)
PAGINATION_RE = re.compile(
    r'<nav\b[^>]*class=["\'][^"\']*\bal-pagination\b[^"\']*["\'][^>]*>'
    r".*?</nav>",
    re.I | re.S,
)
RELAY_ANCHOR_RE = re.compile(
    r'<div\s+id=["\']relay-table["\']\s*></div>', re.I
)
TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", re.I | re.S)
ROW_RE = re.compile(r"<tr\b[^>]*>.*?</tr>", re.I | re.S)
PAGINATED_RE = re.compile(r"^(?P<stem>.+)-page-(?P<number>[0-9]+)\.html$")
DETAIL_PAGE_RE = re.compile(r"^page-(?P<number>[0-9]+)\.html$")
WHITESPACE_RE = re.compile(r"\s+")
RELATIVE_TIME_RE = re.compile(
    r"\b(?:UP\s+|DOWN\s+)?(?:\d+(?:y|mo|w|d|h|m|s)\s*){1,3}ago\b"
    r"|\b\d+\s+(?:minutes?|hours?|days?)\s+ago\b"
    r"|\bjust now\b|\bin the future\b",
    re.I,
)
HTTP_DATE_RE = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d{2}\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"\d{4}\s+\d{2}:\d{2}:\d{2}\s+GMT\b"
)
RUNTIME_CHECK_RE = re.compile(
    r"(?<=Checked: )\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)?"
)
LATENCY_TITLE_RE = re.compile(r"Response time: \d+ ms")
LATENCY_VALUE_RE = re.compile(
    r'(<span title="Response time: <runtime-latency>[^\"]*">)\d+(</span>)'
)
RELAY_RUNTIME_DAYS_RE = re.compile(
    r"(<strong>)\d+(?:\.\d+)?d(</strong>\s*"
    r"<span\b[^>]*>\(R\)</span>)",
    re.I,
)
RELAY_UPTIME_TITLE_RE = re.compile(r"Relay Uptime: \d+(?:\.\d+)?d")
RELAY_UPTIME_VALUE_RE = re.compile(
    r'(<span\b[^>]*title="Relay Uptime: <runtime-days>[^\"]*">)'
    r'\d+(?:\.\d+)?d'
)
RELAY_UPTIME_STATUS_RE = re.compile(
    r'(<span class=")al-status-(?:success|warning|danger)'
    r'(" title="Relay Uptime: <runtime-days>)'
)
GROUP_OVERLOAD_WITH_RELAYS_RE = re.compile(
    r'<li><strong><span title="Relays in this group currently flagged as '
    r'overloaded\.[^"]*">Overloaded</span>:</strong>.*?</ul></li>',
    re.I | re.S,
)
GROUP_OVERLOAD_SIMPLE_RE = re.compile(
    r'<li><strong><span title="Relays in this group currently flagged as '
    r'overloaded\.[^"]*">Overloaded</span>:</strong>.*?</li>',
    re.I | re.S,
)
CONTACT_OVERLOAD_BADGE_RE = re.compile(
    r'<a\b[^>]*href=["\'][^"\']*relay/[A-Fa-f0-9]{40}/#overload["\']'
    r'[^>]*>.*?</a>',
    re.I | re.S,
)
NETWORK_RUNTIME_METRIC_RE = re.compile(
    r'<div class="metric-item"[^>]*>(?:(?!</div>).)*?'
    r'<span class="metric-label">'
    r'(?:Overloaded|New 1d|New 1mo|New 6mo|New 1y)'
    r'</span>\s*</div>',
    re.I | re.S,
)
RELAY_RUNTIME_SECTION_RE = re.compile(
    r'<section id="(?:flags|uptime)"[^>]*>.*?</section>', re.I | re.S
)
RELAY_STABILITY_ROW_RE = re.compile(
    r'<div class="health-row">\s*'
    r'<dt title="Relay stability: overload status and uptime\.">'
    r'.*?</div>',
    re.I | re.S,
)
STATUS_CELL_NOWRAP_RE = re.compile(
    r'(<td)\s+style=["\']white-space:\s*nowrap;?["\']'
    r'(\s*>\s*<span class=["\']circle circle-(?:online|offline)["\'])',
    re.I,
)
OVERLOAD_SORT_COUNT_RE = re.compile(
    r'(Overloaded relays are shown first)\s*'
    r'\(\d+ currently overloaded\)',
    re.I,
)
VETERAN_DAY_RE = re.compile(
    r'(Online and serving traffic since first day:\s*)\d+(\s+days\s+\*)',
    re.I,
)
VETERAN_SCORE_VALUE_RE = re.compile(
    r'(<span title="Veteran Score Calculation:[^"]*">)\d+(</span>)',
    re.I,
)
VETERAN_SPECIALIZATION_VALUE_RE = re.compile(
    r'(<span title="Network longevity specialization:[^"]*">)'
    r'\d+(?=\s+days\s+\*)',
    re.I,
)
GENERAL_OVERLOAD_ISSUE_RE = re.compile(
    r'<li style="margin-bottom:\s*5px;">\s*'
    r'<span class="al-status-danger-bold">\s*General Overload Active\s*'
    r'</span>:.*?</li>',
    re.I | re.S,
)
RECENT_OVERLOAD_NOTES_RE = re.compile(
    r'<div style="margin-top:\s*10px;[^"]*">\s*'
    r'<strong class="al-status-info">Notes:</strong>\s*'
    r'<ul[^>]*>\s*<li[^>]*>Recent Overload Reported:.*?</li>\s*'
    r'</ul>\s*</div>',
    re.I | re.S,
)
EMPTY_ISSUES_BOX_RE = re.compile(
    r'<div style="margin-top:\s*12px;[^"]*">\s*'
    r'<strong class="al-status-warning">Issues Detected:</strong>\s*'
    r'<ul[^>]*>\s*</ul>\s*</div>',
    re.I | re.S,
)


def normalize_runtime_values(html):
    # The inputs are byte-identical, but these views deliberately compare
    # event timestamps and relay lifetimes to wall-clock time at generation.
    # Remove only the named clock-derived surfaces from equivalence checks.
    html = GROUP_OVERLOAD_WITH_RELAYS_RE.sub("", html)
    html = GROUP_OVERLOAD_SIMPLE_RE.sub("", html)
    html = CONTACT_OVERLOAD_BADGE_RE.sub("", html)
    html = NETWORK_RUNTIME_METRIC_RE.sub("", html)
    html = RELAY_RUNTIME_SECTION_RE.sub("", html)
    html = RELAY_STABILITY_ROW_RE.sub("", html)
    html = GENERAL_OVERLOAD_ISSUE_RE.sub("", html)
    html = RECENT_OVERLOAD_NOTES_RE.sub("", html)
    html = EMPTY_ISSUES_BOX_RE.sub("", html)
    html = STATUS_CELL_NOWRAP_RE.sub(r"\1\2", html)
    html = OVERLOAD_SORT_COUNT_RE.sub(
        r"\1 (<runtime-count> currently overloaded)", html
    )
    html = VETERAN_DAY_RE.sub(r"\1<runtime-days>\2", html)
    html = VETERAN_SCORE_VALUE_RE.sub(
        r"\1<runtime-days>\2", html
    )
    html = VETERAN_SPECIALIZATION_VALUE_RE.sub(
        r"\1<runtime-days>", html
    )
    html = RELATIVE_TIME_RE.sub("<relative-time>", html)
    html = re.sub(
        r"\b(?:UP|DOWN)\s+<relative-time>", "<relative-time>", html,
        flags=re.I,
    )
    html = HTTP_DATE_RE.sub("<http-date>", html)
    html = RUNTIME_CHECK_RE.sub("<runtime-check>", html)
    html = LATENCY_TITLE_RE.sub("Response time: <runtime-latency>", html)
    html = LATENCY_VALUE_RE.sub(r"\1<runtime-latency>\2", html)
    html = RELAY_RUNTIME_DAYS_RE.sub(r"\1<runtime-days>\2", html)
    html = RELAY_UPTIME_TITLE_RE.sub("Relay Uptime: <runtime-days>", html)
    html = RELAY_UPTIME_VALUE_RE.sub(r"\1<runtime-days>", html)
    html = RELAY_UPTIME_STATUS_RE.sub(r"\1<runtime-status>\2", html)
    return html


def clean_internal_hrefs(html):
    def replacement(match):
        value = match.group("value")
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or value.startswith(("#", "//")):
            return match.group(0)
        path = parsed.path
        if not path.endswith(".html"):
            return match.group(0)
        if path.endswith("/index.html"):
            path = path[:-10]
        elif path == "index.html":
            path = "./"
        else:
            path = path[:-5]
        rewritten = urlunsplit(("", "", path, parsed.query, parsed.fragment))
        quote = match.group("quote")
        return f"{match.group('prefix')}{quote}{rewritten}{quote}"

    return HREF_RE.sub(replacement, html)


def normalize_common_html(html):
    html = HEAD_RE.sub("<head></head>", html, count=1)
    html = PAGINATION_RE.sub("", html)
    html = RELAY_ANCHOR_RE.sub("", html)
    html = clean_internal_hrefs(html)
    html = re.sub(r'\s+class=["\']page-title["\']', "", html, flags=re.I)
    html = re.sub(
        r'(<h1\b[^>]*?)\s+class=["\']page-title["\']', r"\1", html,
        flags=re.I,
    )
    html = re.sub(r"<(/?)h1\b", r"<\1h2", html, flags=re.I)
    html = normalize_runtime_values(html)
    return WHITESPACE_RE.sub(" ", html).strip()


def base_path_for_added(relative):
    path = Path(relative)
    detail = DETAIL_PAGE_RE.match(path.name)
    if detail and int(detail.group("number")) >= 2:
        return (path.parent / "index.html").as_posix()
    paginated = PAGINATED_RE.match(path.name)
    if paginated and int(paginated.group("number")) >= 2:
        return (path.parent / f"{paginated.group('stem')}.html").as_posix()
    return None


def table_rows(html, base_relative):
    rows = []
    is_misc_listing = base_relative.startswith("misc/") and any(
        f"misc/{name}-by-" in base_relative
        for name in ("contacts", "countries", "families", "networks", "platforms")
    )
    for row in ROW_RE.findall(html):
        if "<td" not in row.lower():
            continue
        if not is_misc_listing and not re.search(
            r'href=["\'][^"\']*relay/[A-Fa-f0-9]{40}/', row, re.I
        ):
            continue
        normalized = clean_internal_hrefs(row)
        normalized = normalize_runtime_values(normalized)
        rows.append(WHITESPACE_RE.sub(" ", normalized).strip())
    return Counter(rows)


def normalize_overload_sort_order(html):
    """Sort relay rows by stable content for clock-derived overload views."""
    def table_replacement(table_match):
        table = table_match.group(0)
        rows = ROW_RE.findall(table)
        relay_rows = [
            row for row in rows
            if re.search(
                r'href=["\'][^"\']*relay/[A-Fa-f0-9]{40}/', row, re.I
            )
        ]
        if not relay_rows:
            return table
        relay_rows.sort(
            key=lambda row: WHITESPACE_RE.sub(
                " ", normalize_runtime_values(clean_internal_hrefs(row))
            ).strip()
        )
        sorted_rows = iter(relay_rows)

        def row_replacement(row_match):
            row = row_match.group(0)
            if re.search(
                r'href=["\'][^"\']*relay/[A-Fa-f0-9]{40}/', row, re.I
            ):
                return next(sorted_rows)
            return row

        return ROW_RE.sub(row_replacement, table)

    return TABLE_RE.sub(table_replacement, html)


def head_contract(html, relative, expected_origin):
    failures = []
    head_match = HEAD_RE.search(html)
    if not head_match:
        return [f"{relative}: missing complete head"]
    head = head_match.group(0)
    canonical_matches = re.findall(
        r'<link\b[^>]*\brel=["\'][^"\']*\bcanonical\b[^"\']*["\'][^>]*>',
        head,
        re.I,
    )
    if len(canonical_matches) != 1:
        failures.append(
            f"{relative}: expected one canonical, found {len(canonical_matches)}"
        )
    elif ".html" in canonical_matches[0]:
        failures.append(f"{relative}: canonical contains .html")
    for signal, pattern in (
        ("description", r'<meta\b[^>]*\bname=["\']description["\'][^>]*>'),
        ("og:title", r'<meta\b[^>]*\bproperty=["\']og:title["\'][^>]*>'),
        ("og:description", r'<meta\b[^>]*\bproperty=["\']og:description["\'][^>]*>'),
        ("favicon", r'<link\b[^>]*\brel=["\']icon["\'][^>]*>'),
        ("Google verification", r'<meta\b[^>]*\bname=["\']google-site-verification["\'][^>]*>'),
        ("Bing verification", r'<meta\b[^>]*\bname=["\']msvalidate\.01["\'][^>]*>'),
    ):
        count = len(re.findall(pattern, head, re.I))
        if count != 1:
            failures.append(f"{relative}: expected one {signal}, found {count}")
    h1_count = len(re.findall(r"<h1\b", html, re.I))
    if h1_count != 1:
        failures.append(f"{relative}: expected one h1, found {h1_count}")

    for match in HREF_RE.finditer(html):
        value = match.group("value")
        parsed = urlsplit(value)
        internal = (
            (not parsed.scheme and not parsed.netloc)
            or (parsed.scheme in ("http", "https") and parsed.netloc == expected_origin)
        )
        if internal and parsed.path.endswith(".html"):
            failures.append(f"{relative}: internal .html href remains: {value}")
            break
    return failures


def _compare_common_worker(args):
    before_path, after_path, relative, origin_host, is_paginated = args
    before = Path(before_path).read_text(encoding="utf-8")
    after = Path(after_path).read_text(encoding="utf-8")
    failures = head_contract(after, relative, origin_host)
    if re.match(r"^contact/[^/]+/by-overload\.html$", relative):
        before = normalize_overload_sort_order(before)
        after = normalize_overload_sort_order(after)
    if is_paginated:
        return "paginated", failures
    if relative == "misc/diagnostics.html":
        return "diagnostics", failures
    if normalize_common_html(before) == normalize_common_html(after):
        return "unchanged", failures
    failures.append(f"unexpected normalized body change: {relative}")
    return "changed", failures


def _compare_pagination_worker(args):
    baseline_path, after_base_path, base, added_paths, origin_host = args
    before = Path(baseline_path).read_text(encoding="utf-8")
    combined = table_rows(Path(after_base_path).read_text(encoding="utf-8"), base)
    failures = []
    for relative, path in added_paths:
        page_html = Path(path).read_text(encoding="utf-8")
        failures.extend(head_contract(page_html, relative, origin_host))
        combined.update(table_rows(page_html, base))
    expected_rows = table_rows(before, base)
    if expected_rows != combined:
        missing_count = sum((expected_rows - combined).values())
        extra_count = sum((combined - expected_rows).values())
        failures.append(
            f"pagination row mismatch for {base}: "
            f"missing={missing_count} extra={extra_count}"
        )
        return False, failures
    return True, failures


def compare(baseline_dir, after_dir, origin, workers=None):
    baseline_files = {
        path.relative_to(baseline_dir).as_posix(): path
        for path in baseline_dir.rglob("*.html") if path.is_file()
    }
    after_files = {
        path.relative_to(after_dir).as_posix(): path
        for path in after_dir.rglob("*.html") if path.is_file()
    }
    removed = sorted(baseline_files.keys() - after_files.keys())
    added = sorted(after_files.keys() - baseline_files.keys())
    common = sorted(baseline_files.keys() & after_files.keys())

    failures = [f"removed HTML file: {item}" for item in removed]
    pagination_groups = {}
    for relative in added:
        base = base_path_for_added(relative)
        if not base or base not in baseline_files:
            failures.append(f"unexpected non-pagination HTML addition: {relative}")
            continue
        pagination_groups.setdefault(base, []).append(relative)

    origin_host = urlsplit(origin).netloc
    identical_normalized = expected_normalized = 0
    diagnostics_volatile = 0
    common_tasks = [
        (
            str(baseline_files[relative]),
            str(after_files[relative]),
            relative,
            origin_host,
            relative in pagination_groups,
        )
        for relative in common
    ]
    max_workers = workers or min(8, os.cpu_count() or 1)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        common_results = executor.map(
            _compare_common_worker, common_tasks, chunksize=24
        )
        for result, result_failures in common_results:
            failures.extend(result_failures)
            if result == "paginated":
                expected_normalized += 1
            elif result == "diagnostics":
                diagnostics_volatile += 1
            elif result == "unchanged":
                identical_normalized += 1

    pagination_tasks = []
    for base, added_pages in sorted(pagination_groups.items()):
        pagination_tasks.append(
            (
                str(baseline_files[base]),
                str(after_files[base]),
                base,
                [(relative, str(after_files[relative]))
                 for relative in sorted(added_pages)],
                origin_host,
            )
        )

    row_groups_verified = 0
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        pagination_results = executor.map(
            _compare_pagination_worker, pagination_tasks, chunksize=4
        )
        for verified, result_failures in pagination_results:
            failures.extend(result_failures)
            if verified:
                row_groups_verified += 1

    return {
        "baseline_html_count": len(baseline_files),
        "after_html_count": len(after_files),
        "common_html_count": len(common),
        "removed_html_count": len(removed),
        "added_pagination_html_count": len(added),
        "paginated_base_count": len(pagination_groups),
        "pagination_row_groups_verified": row_groups_verified,
        "normalized_bodies_unchanged": identical_normalized,
        "paginated_common_bodies_expected": expected_normalized,
        "volatile_diagnostics_pages": diagnostics_volatile,
        "failure_count": len(failures),
        "failures": failures[:100],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline")
    parser.add_argument("after")
    parser.add_argument("--origin", default="https://metrics.1aeo.com")
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    report = compare(
        Path(args.baseline), Path(args.after), args.origin, workers=args.workers
    )
    print(json.dumps(report, indent=2))
    return 1 if report["failure_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
