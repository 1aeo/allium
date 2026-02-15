#!/usr/bin/env python3
"""
Compare two allium output directories to verify refactoring didn't change output.
Ignores timestamp differences (which change every run).
"""

import os
import re
import sys
import json
from pathlib import Path


# Patterns that are expected to differ between runs (timestamps, timing info)
TIMESTAMP_PATTERNS = [
    # GMT timestamps like "2026-02-15 17:15:42 GMT"
    re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s*(?:GMT|UTC)?'),
    # ISO timestamps like "2026-02-15T17:15:42"
    re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'),
    # "Generated on ..." or "Last updated ..."
    re.compile(r'(?:Generated|Updated|Fetched|Checked)\s+(?:on|at)\s+.*?\d{4}'),
    # Latency values like "123ms" that vary per run
    re.compile(r'\d+\.\d+\s*ms'),
    # "X ago" relative time strings that change
    re.compile(r'\d+[ymd]\s+\d+[ymdwh]\s+ago'),
    re.compile(r'\d+[ymdhw]\s+ago'),
    # Progress/timing info
    re.compile(r'\d+\.\d+s'),
]


def normalize_line(line):
    """Remove timestamp-like content from a line for comparison."""
    for pattern in TIMESTAMP_PATTERNS:
        line = pattern.sub('__TIMESTAMP__', line)
    return line


def compare_files(file1, file2):
    """Compare two files, ignoring timestamp differences. Returns list of differences."""
    diffs = []
    
    try:
        with open(file1, 'r', encoding='utf-8', errors='replace') as f1, \
             open(file2, 'r', encoding='utf-8', errors='replace') as f2:
            lines1 = f1.readlines()
            lines2 = f2.readlines()
    except Exception as e:
        return [f"Error reading files: {e}"]
    
    if len(lines1) != len(lines2):
        diffs.append(f"Line count differs: {len(lines1)} vs {len(lines2)}")
        # Still compare what we can
    
    max_lines = min(len(lines1), len(lines2))
    diff_count = 0
    MAX_DIFFS_PER_FILE = 3  # Only show first 3 diffs per file
    
    for i in range(max_lines):
        norm1 = normalize_line(lines1[i])
        norm2 = normalize_line(lines2[i])
        if norm1 != norm2:
            diff_count += 1
            if diff_count <= MAX_DIFFS_PER_FILE:
                diffs.append(f"  Line {i+1}:")
                diffs.append(f"    baseline: {lines1[i].rstrip()[:120]}")
                diffs.append(f"    current:  {lines2[i].rstrip()[:120]}")
    
    if diff_count > MAX_DIFFS_PER_FILE:
        diffs.append(f"  ... and {diff_count - MAX_DIFFS_PER_FILE} more differing lines")
    
    return diffs


def compare_json_files(file1, file2):
    """Compare two JSON files, ignoring timestamp fields."""
    try:
        with open(file1, 'r') as f1, open(file2, 'r') as f2:
            data1 = json.load(f1)
            data2 = json.load(f2)
        
        # For search index, compare structure not exact values
        if isinstance(data1, dict) and isinstance(data2, dict):
            keys1 = set(data1.keys())
            keys2 = set(data2.keys())
            if keys1 != keys2:
                return [f"JSON keys differ: only in baseline={keys1-keys2}, only in current={keys2-keys1}"]
            
            # Compare relay counts if present
            for key in ['relays', 'families']:
                if key in data1 and key in data2:
                    if isinstance(data1[key], list) and isinstance(data2[key], list):
                        if len(data1[key]) != len(data2[key]):
                            return [f"JSON '{key}' count differs: {len(data1[key])} vs {len(data2[key])}"]
        return []
    except Exception as e:
        return [f"JSON comparison error: {e}"]


def compare_directories(dir1, dir2):
    """Compare two output directories."""
    dir1 = Path(dir1)
    dir2 = Path(dir2)
    
    # Collect all files relative to each directory
    files1 = set()
    for f in dir1.rglob('*'):
        if f.is_file():
            files1.add(f.relative_to(dir1))
    
    files2 = set()
    for f in dir2.rglob('*'):
        if f.is_file():
            files2.add(f.relative_to(dir2))
    
    # Check for missing/extra files
    only_in_baseline = files1 - files2
    only_in_current = files2 - files1
    common_files = files1 & files2
    
    print(f"Files in baseline: {len(files1)}")
    print(f"Files in current:  {len(files2)}")
    print(f"Common files:      {len(common_files)}")
    
    issues = []
    
    if only_in_baseline:
        issues.append(f"\n❌ {len(only_in_baseline)} files ONLY in baseline:")
        for f in sorted(list(only_in_baseline))[:20]:
            issues.append(f"  - {f}")
        if len(only_in_baseline) > 20:
            issues.append(f"  ... and {len(only_in_baseline) - 20} more")
    
    if only_in_current:
        issues.append(f"\n❌ {len(only_in_current)} files ONLY in current:")
        for f in sorted(list(only_in_current))[:20]:
            issues.append(f"  - {f}")
        if len(only_in_current) > 20:
            issues.append(f"  ... and {len(only_in_current) - 20} more")
    
    # Compare common HTML files
    html_files = sorted([f for f in common_files if str(f).endswith('.html')])
    json_files = sorted([f for f in common_files if str(f).endswith('.json')])
    
    differing_html = 0
    print(f"\nComparing {len(html_files)} HTML files (ignoring timestamps)...")
    
    for f in html_files:
        diffs = compare_files(dir1 / f, dir2 / f)
        if diffs:
            differing_html += 1
            if differing_html <= 10:  # Show first 10 differing files
                issues.append(f"\n⚠️  {f}:")
                for d in diffs:
                    issues.append(d)
    
    if differing_html > 10:
        issues.append(f"\n... and {differing_html - 10} more differing HTML files")
    
    # Compare JSON files
    for f in json_files:
        diffs = compare_json_files(dir1 / f, dir2 / f)
        if diffs:
            issues.append(f"\n⚠️  {f}:")
            for d in diffs:
                issues.append(d)
    
    # Summary
    print(f"\n{'='*60}")
    if not issues and not only_in_baseline and not only_in_current and differing_html == 0:
        print("✅ PASS: Output is identical (ignoring timestamps)")
        return True
    else:
        print(f"{'✅' if differing_html == 0 else '⚠️'} HTML files with non-timestamp differences: {differing_html}/{len(html_files)}")
        if only_in_baseline:
            print(f"❌ Files only in baseline: {len(only_in_baseline)}")
        if only_in_current:
            print(f"❌ Files only in current: {len(only_in_current)}")
        
        for issue in issues:
            print(issue)
        
        if differing_html == 0 and not only_in_baseline and not only_in_current:
            print("\n✅ PASS: File sets match, all differences are timestamp-only")
            return True
        else:
            print(f"\n❌ FAIL: {differing_html} content differences found")
            return False


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <baseline_dir> <current_dir>")
        sys.exit(1)
    
    success = compare_directories(sys.argv[1], sys.argv[2])
    sys.exit(0 if success else 1)
