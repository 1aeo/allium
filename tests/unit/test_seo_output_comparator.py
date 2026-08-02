"""Regression tests for wall-clock normalization in the SEO output comparator."""

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from compare_seo_outputs import normalize_runtime_values  # noqa: E402


def test_normalizes_runtime_status_cell_nowrap_style():
    styled = (
        '<td style="white-space: nowrap;">'
        '<span class="circle circle-online"></span></td>'
    )
    plain = '<td><span class="circle circle-online"></span></td>'

    assert normalize_runtime_values(styled) == normalize_runtime_values(plain)


def test_normalizes_veteran_score_day_boundary():
    before = (
        '<span title="Veteran Score Calculation: Online and serving traffic '
        'since first day: 5904 days * 1.0 (1 relays)">5904</span>'
        '<span title="Network longevity specialization: Online and serving '
        'traffic since first day: 5904 days * 1.0 (1 relays)">'
        '5904 days * 1.0...</span>'
    )
    after = before.replace("5904", "5905")

    assert normalize_runtime_values(before) == normalize_runtime_values(after)


def test_normalizes_overload_threshold_transition():
    active = (
        '<div style="margin-top: 12px; padding: 10px;">'
        '<strong class="al-status-warning">Issues Detected:</strong>'
        '<ul><li style="margin-bottom: 5px;">'
        '<span class="al-status-danger-bold">General Overload Active</span>:'
        ' Relay reported general overload at 2026-07-30 08:00 UTC.'
        '<br><span>Suggestion: inspect the relay.</span></li></ul></div>'
    )
    recent = (
        '<div style="margin-top: 10px; padding: 10px;">'
        '<strong class="al-status-info">Notes:</strong>'
        '<ul><li style="font-size: 12px;">Recent Overload Reported: '
        'Relay reported overload 3 days ago (no longer active per 72h threshold).'
        '</li></ul></div>'
    )

    assert normalize_runtime_values(active) == normalize_runtime_values(recent)


def test_normalizes_overload_sort_count_without_removing_banner():
    one = (
        '<p class="al-status-danger-bold">'
        '⚡︎ Overloaded relays are shown first (1 currently overloaded).'
        '</p>'
    )
    two = one.replace("(1 currently", "(2 currently")

    normalized = normalize_runtime_values(one)
    assert normalized == normalize_runtime_values(two)
    assert "Overloaded relays are shown first" in normalized
