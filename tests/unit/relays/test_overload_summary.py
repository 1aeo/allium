"""Tests for the group-level Overloaded summary (helper, wiring, and rendering).

Consolidated single file: pure helper unit tests, build_template_args wiring
tests against ONE shared module-scoped Relays instance, and template render
tests for the overload_bullet macro / detail_summary / contact.html placement.
"""

import pytest

from allium.lib.page_writer import build_template_args
from allium.lib.stability_utils import compute_group_overload_summary

SAMPLE_RELAYS = [
    {'nickname': 'BigRelay', 'fingerprint': 'A' * 40, 'observed_bandwidth': 2000000,
     'stability_is_overloaded': True, 'stability_tooltip': 'Rate limits hit W:2 R:0 (limit: 10 MB/s)'},
    {'nickname': 'SmallRelay', 'fingerprint': 'B' * 40, 'observed_bandwidth': 1000000,
     'stability_is_overloaded': True, 'stability_tooltip': 'FD exhaustion reported'},
]
SAMPLE_SUMMARY = {'overloaded': 2, 'total': 10, 'pct_formatted': '20.0%', 'relays': SAMPLE_RELAYS}


# ---------------------------------------------------------------------------
# Helper unit tests (pure dicts, no Relays pipeline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('members,expected', [
    ([], None),                                                      # empty group
    ([{'stability_is_overloaded': False}, {}], None),                # zero overloaded / missing key
    ([{'stability_is_overloaded': True}] * 3
     + [{'stability_is_overloaded': False}] * 5,
     {'overloaded': 3, 'total': 8, 'pct_formatted': '37.5%',
      'relays': [{'stability_is_overloaded': True}] * 3}),           # mixed
    ([{'stability_is_overloaded': True}] * 4,
     {'overloaded': 4, 'total': 4, 'pct_formatted': '100.0%',
      'relays': [{'stability_is_overloaded': True}] * 4}),           # all overloaded
    ([{'stability_is_overloaded': True}, {}, {'nickname': 'x'}],
     {'overloaded': 1, 'total': 3, 'pct_formatted': '33.3%',
      'relays': [{'stability_is_overloaded': True}]}),               # missing keys mixed in
])
def test_compute_group_overload_summary(members, expected):
    assert compute_group_overload_summary(members) == expected


def test_summary_relays_are_references_in_impact_order():
    """'relays' holds the member dicts themselves (no copies), sorted by
    observed_bandwidth desc; missing bandwidth is treated as 0 (sorts last)."""
    small = {'stability_is_overloaded': True, 'observed_bandwidth': 1, 'nickname': 's'}
    big = {'stability_is_overloaded': True, 'observed_bandwidth': 9, 'nickname': 'b'}
    no_bw = {'stability_is_overloaded': True, 'nickname': 'n'}
    summary = compute_group_overload_summary([small, {'healthy': True}, big, no_bw])
    assert [r['nickname'] for r in summary['relays']] == ['b', 's', 'n']
    assert summary['relays'][0] is big  # reference, not a copy


def test_tiny_fraction_uses_floor():
    """1 of 3000 would round to 0.0% — must show <0.1% instead."""
    members = [{'stability_is_overloaded': True}] + [{}] * 2999
    assert compute_group_overload_summary(members)['pct_formatted'] == '<0.1%'
    # Boundary: 1 of 1250 = 0.08% is >= 0.05 so .1f rounds it up to "0.1%"
    members = [{'stability_is_overloaded': True}] + [{}] * 1249
    assert compute_group_overload_summary(members)['pct_formatted'] == '0.1%'


# ---------------------------------------------------------------------------
# build_template_args wiring — shared overload_relay_set fixture from
# tests/conftest.py (module-scoped; one expensive Relays init for all tests)
# ---------------------------------------------------------------------------

def _args(relay_set, page_key):
    value, group = next(iter(relay_set.json['sorted'][page_key].items()))
    return build_template_args(relay_set, page_key, value, group, [], set())


@pytest.mark.parametrize('page_key', ['contact', 'family', 'as'])
def test_build_template_args_includes_overload_summary(overload_relay_set, page_key):
    summary = _args(overload_relay_set, page_key)['overload_summary']
    assert (summary['overloaded'], summary['total'], summary['pct_formatted']) == (2, 4, '50.0%')
    # relays 0 and 1 are the overloaded ones (fixture flags i < 2)
    assert sorted(r['fingerprint'] for r in summary['relays']) == [f'{i:040d}' for i in range(2)]


def test_build_template_args_skips_out_of_scope_pages(overload_relay_set):
    """Country pages must not get an overload_summary (out of requested scope)."""
    assert _args(overload_relay_set, 'country')['overload_summary'] is None


def test_build_template_args_hides_when_zero_overloaded(overload_relay_set):
    relays = overload_relay_set.json['relays']
    saved = [r['stability_is_overloaded'] for r in relays]
    try:
        for r in relays:
            r['stability_is_overloaded'] = False
        assert _args(overload_relay_set, 'contact')['overload_summary'] is None
    finally:
        for r, flag in zip(relays, saved):
            r['stability_is_overloaded'] = flag


# ---------------------------------------------------------------------------
# Template rendering (jinja_env fixture from tests/conftest.py)
# ---------------------------------------------------------------------------

DETAIL_SUMMARY_CALL = """
{% from 'macros.html' import detail_summary %}
{{ detail_summary(
    '10.0', 'MB/s', '4.0', '3.0', '3.0',
    0.01, 0.01, 0.01, 0.01,
    2, 1, 1, 10,
    {'formatted_string': 'Mixed (10 relays)'},
    overload_summary=overload_summary,
    exit_dns_health_summary=exit_dns_health_summary
) }}
"""

DNS_SUMMARY = {'exit_count': 3, 'healthy': 3, 'failing': 0, 'untested': 0,
               'healthy_pct': 100, 'failing_pct': 0, 'untested_pct': 0}


def _render_detail_summary(jinja_env, overload_summary=None, exit_dns_health_summary=None):
    return jinja_env.from_string(DETAIL_SUMMARY_CALL).render(
        overload_summary=overload_summary,
        exit_dns_health_summary=exit_dns_health_summary,
        base_url=None, validated_aroi_domains=set())


def test_detail_summary_shows_overload_before_dns(jinja_env):
    rendered = _render_detail_summary(jinja_env, SAMPLE_SUMMARY, DNS_SUMMARY)
    assert '20.0% (2 of 10 relays)' in rendered
    assert 'al-status-danger' in rendered
    assert rendered.index('Overloaded') < rendered.index('Exit DNS Health')
    # Regression guard: family/AS pages (via detail_summary) keep the plain
    # bullet — no variant link and no per-relay #overload links.
    assert 'by-overload.html' not in rendered
    assert '#overload' not in rendered


def test_detail_summary_hides_overload_when_none(jinja_env):
    assert 'Overloaded' not in _render_detail_summary(jinja_env)


def test_overload_bullet_macro_singular(jinja_env):
    rendered = jinja_env.from_string(
        "{% from 'macros.html' import overload_bullet %}{{ overload_bullet(summary) }}"
    ).render(summary={'overloaded': 1, 'total': 1, 'pct_formatted': '100.0%'})
    assert '100.0% (1 of 1 relay)' in rendered
    assert '1 relays' not in rendered
    assert '<a ' not in rendered  # defaults render no links at all


BULLET_TMPL = ("{% from 'macros.html' import overload_bullet %}"
               "{{ overload_bullet(summary, link_href, path_prefix) }}")


def _render_bullet(jinja_env, link_href=None, path_prefix=None, summary=SAMPLE_SUMMARY):
    return jinja_env.from_string(BULLET_TMPL).render(
        summary=summary, link_href=link_href, path_prefix=path_prefix)


def test_overload_bullet_link_href_wraps_count(jinja_env):
    rendered = _render_bullet(jinja_env, link_href='by-overload.html#relay-table')
    assert '<a href="by-overload.html#relay-table" class="al-status-danger"' in rendered
    assert '20.0% (2 of 10 relays)' in rendered


def test_overload_bullet_path_prefix_renders_expanded_relay_links(jinja_env):
    rendered = _render_bullet(jinja_env, path_prefix='../../')
    # Every overloaded relay linked straight to its #overload detail section
    assert f'href="../../relay/{"A" * 40}/#overload"' in rendered
    assert f'href="../../relay/{"B" * 40}/#overload"' in rendered
    assert '>BigRelay</a>' in rendered and '>SmallRelay</a>' in rendered
    # Impact order (highest bandwidth first) and reason tooltips
    assert rendered.index('BigRelay') < rendered.index('SmallRelay')
    assert 'Rate limits hit W:2 R:0 (limit: 10 MB/s)' in rendered
    # Fully expanded per user requirement — no collapse mechanism
    assert '<details' not in rendered


def test_overload_bullet_no_relay_list_without_path_prefix(jinja_env):
    rendered = _render_bullet(jinja_env, link_href='by-overload.html#relay-table')
    assert '#overload' not in rendered.replace('by-overload.html', '')


def _contact_context(overload_summary):
    relay = {
        'aroi_domain': 'example.org', 'country': 'us', 'country_name': 'United States',
        'observed_bandwidth': 1000000, 'nickname': 'TestRelay',
        'fingerprint': 'ABC123DEF456', 'running': True,
        'flags': ['Running', 'Valid'], 'flags_escaped': ['Running', 'Valid'],
        'flags_lower_escaped': ['running', 'valid'], 'effective_family': [],
        'measured': True, 'uptime_display': 'UP 5d 12h', 'uptime_api_display': '99.5%',
        'or_addresses': ['192.168.1.1:9001'], 'as': 'AS7922', 'as_name': 'Comcast Cable',
        'platform': 'Linux', 'first_seen': '2023-01-01 12:00:00',
        'first_seen_date_escaped': '2023-01-01', 'contact_md5': 'abcd1234',
        'contact': 'test@example.com',
    }
    return {
        'contact': 'test@example.com', 'contact_hash': 'abcd1234',
        'bandwidth': '150.0', 'bandwidth_unit': 'MB/s',
        'consensus_weight_fraction': 0.025,
        'network_position': {'label': 'mixed', 'formatted_string': 'Mixed (5 total relays)'},
        'relay_subset': [relay],
        'relays': {'json': {'relay_subset': [relay]}, 'use_bits': False},
        'page_ctx': {'path_prefix': '../'},
        'contact_display_data': {'bandwidth_breakdown': '50.0 MB/s guard',
                                 'consensus_weight_breakdown': '1.0% guard',
                                 'operator_intelligence': {}},
        'contact_rankings': [], 'operator_reliability': None,
        'contact_validation_status': None, 'aroi_validation_timestamp': None,
        'is_validated_aroi': False, 'primary_country_data': None,
        'exit_dns_health_summary': {**DNS_SUMMARY, 'exit_count': 2, 'healthy': 2},
        'overload_summary': overload_summary,
        'guard_count': 1, 'middle_count': 1, 'exit_count': 1,
        'base_url': None, 'validated_aroi_domains': set(),
        'sortable_scope': 'none', 'contact_sort_mode': None,
        'contact_sort_links': {}, 'contact_sort_enabled': False,
        'contact_has_ipv6': False,
    }


def test_contact_html_shows_overload_before_dns(jinja_env):
    rendered = jinja_env.get_template('contact.html').render(**_contact_context(SAMPLE_SUMMARY))
    assert '20.0% (2 of 10 relays)' in rendered
    assert rendered.index('Overloaded') < rendered.index('Exit DNS Health')


def test_contact_html_hides_overload_when_none(jinja_env):
    rendered = jinja_env.get_template('contact.html').render(**_contact_context(None))
    assert 'Overloaded' not in rendered


def test_contact_html_bullet_lists_overloaded_relays_expanded(jinja_env):
    """Option 2: all overloaded relays linked to their #overload sections,
    fully expanded (no collapse), even when the sort variant doesn't exist."""
    rendered = jinja_env.get_template('contact.html').render(**_contact_context(SAMPLE_SUMMARY))
    assert f'href="../relay/{"A" * 40}/#overload"' in rendered
    assert f'href="../relay/{"B" * 40}/#overload"' in rendered
    assert '<details' not in rendered
    # No by-overload.html variant for this contact (contact_sort_links={}) -> unlinked count
    assert 'by-overload.html' not in rendered


def test_contact_html_bullet_count_links_variant_when_available(jinja_env):
    """Option 1: the count links to the by-overload.html sort variant."""
    context = _contact_context(SAMPLE_SUMMARY)
    context['contact_sort_links'] = {'overload': 'by-overload.html'}
    rendered = jinja_env.get_template('contact.html').render(**context)
    assert '<a href="by-overload.html#relay-table" class="al-status-danger"' in rendered
    assert '20.0% (2 of 10 relays)' in rendered


def test_contact_relay_row_overload_badge(jinja_env):
    """Option 1: overloaded relays get a ⚡ in the Status column linking to
    their #overload section; healthy relays get no badge."""
    context = _contact_context(SAMPLE_SUMMARY)
    relay = context['relay_subset'][0]
    relay['stability_is_overloaded'] = True
    relay['stability_tooltip'] = 'General overload at 2026-07-31 06:12 UTC'
    rendered = jinja_env.get_template('contact.html').render(**context)
    assert '⚡' in rendered
    assert f'href="../relay/{relay["fingerprint"]}/#overload"' in rendered
    assert 'General overload at 2026-07-31 06:12 UTC. Click for overload details.' in rendered


def test_contact_relay_row_no_badge_when_not_overloaded(jinja_env):
    rendered = jinja_env.get_template('contact.html').render(**_contact_context(None))
    assert '⚡' not in rendered
