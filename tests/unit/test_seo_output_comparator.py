"""Regression tests for wall-clock normalization in the SEO output comparator."""

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from compare_seo_outputs import (  # noqa: E402
    normalize_common_html,
    normalize_network_veteran_order,
    normalize_runtime_values,
)


def test_normalizes_expected_authority_heading_hierarchy_change():
    before = (
        "<html><head><title>Before</title></head><body>"
        "<h3>Directory Authority Status</h3></body></html>"
    )
    after = (
        "<html><head><title>After</title></head><body>"
        "<h2>Directory Authority Status</h2></body></html>"
    )

    assert normalize_common_html(before) == normalize_common_html(after)


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


def test_normalizes_overload_sort_banner_when_count_reaches_zero():
    counted = "Overloaded relays are shown first (1 currently overloaded)."
    zero = "Overloaded relays are shown first."

    assert normalize_runtime_values(counted) == normalize_runtime_values(zero)


def test_normalizes_network_veteran_rank_swaps():
    row_a = (
        '<tr><td><span title="Rank 14 in this category">14</span></td>'
        '<td>Operator A</td></tr>'
    )
    row_b = (
        '<tr><td><span title="Rank 15 in this category">15</span></td>'
        '<td>Operator B</td></tr>'
    )
    before = (
        '<section id="network_veterans"><table>'
        f'{row_a}{row_b}</table></section>'
    )
    after = (
        '<section id="network_veterans"><table>'
        f'{row_b.replace("15", "14")}{row_a.replace("14", "15")}'
        '</table></section>'
    )

    assert normalize_network_veteran_order(before) == (
        normalize_network_veteran_order(after)
    )


def test_normalizes_live_authority_latency_checks():
    healthy = (
        '<li><strong>Latency Status</strong>: 9/9 OK</li>'
        '<td><span title="Response time: 50 ms">50</span></td>'
        '<ul><li>faravahar has low uptime</li></ul>'
    )
    degraded = (
        '<li><strong>Latency Status</strong>: 7/9 OK, 1 down</li>'
        '<td><span class="bad" title="Connection timed out after 2 seconds">'
        'Timeout</span></td>'
        '<ul><li>dizum is not responding (latency check failed)</li>'
        '<li>faravahar has low uptime</li></ul>'
    )

    assert normalize_runtime_values(healthy) == normalize_runtime_values(degraded)
