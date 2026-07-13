"""Tests for the group-level Overloaded summary (helper, wiring, and rendering).

Consolidated single file: pure helper unit tests, build_template_args wiring
tests against ONE shared module-scoped Relays instance, and template render
tests for the overload_bullet macro / detail_summary / contact.html placement.
"""

import pytest

from allium.lib.page_writer import build_template_args
from allium.lib.stability_utils import compute_group_overload_summary

SAMPLE_SUMMARY = {'overloaded': 2, 'total': 10, 'pct_formatted': '20.0%'}


# ---------------------------------------------------------------------------
# Helper unit tests (pure dicts, no Relays pipeline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('members,expected', [
    ([], None),                                                      # empty group
    ([{'stability_is_overloaded': False}, {}], None),                # zero overloaded / missing key
    ([{'stability_is_overloaded': True}] * 3
     + [{'stability_is_overloaded': False}] * 5,
     {'overloaded': 3, 'total': 8, 'pct_formatted': '37.5%'}),       # mixed
    ([{'stability_is_overloaded': True}] * 4,
     {'overloaded': 4, 'total': 4, 'pct_formatted': '100.0%'}),      # all overloaded
    ([{'stability_is_overloaded': True}, {}, {'nickname': 'x'}],
     {'overloaded': 1, 'total': 3, 'pct_formatted': '33.3%'}),       # missing keys mixed in
])
def test_compute_group_overload_summary(members, expected):
    assert compute_group_overload_summary(members) == expected


def test_tiny_fraction_uses_floor():
    """1 of 3000 would round to 0.0% — must show <0.1% instead."""
    members = [{'stability_is_overloaded': True}] + [{}] * 2999
    assert compute_group_overload_summary(members)['pct_formatted'] == '<0.1%'
    # Boundary: 1 of 1250 = 0.08% is >= 0.05 so .1f rounds it up to "0.1%"
    members = [{'stability_is_overloaded': True}] + [{}] * 1249
    assert compute_group_overload_summary(members)['pct_formatted'] == '0.1%'


# ---------------------------------------------------------------------------
# build_template_args wiring — ONE shared Relays instance for all tests
# (full __init__ pipeline is expensive; 4 relays, 2 overloaded)
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def relay_set(tmp_path_factory):
    from allium.lib.relays import Relays

    n = 4
    relays = [{
        'nickname': f'Relay{i}', 'fingerprint': f'{i:040d}', 'running': True,
        'flags': ['Running', 'Valid'], 'observed_bandwidth': 1_000_000,
        'consensus_weight': 100, 'consensus_weight_fraction': 0.01,
        'or_addresses': [f'192.0.2.{i + 1}:9001'],
        'as': 'AS64500', 'as_name': 'Test AS',
        'country': 'us', 'country_name': 'United States', 'platform': 'Linux',
        'first_seen': '2023-01-01 00:00:00', 'last_seen': '2026-07-12 00:00:00',
        'contact': 'ops@example.com', 'measured': True,
        'effective_family': [f'{j:040d}' for j in range(n)],
    } for i in range(n)]

    rs = Relays(output_dir=str(tmp_path_factory.mktemp('overload')),
                onionoo_url='https://test.example.com',
                relay_data={'relays': relays},
                use_bits=False, progress=False, mp_workers=0)
    # Stability is normally set during bandwidth enrichment; apply after init.
    for i, relay in enumerate(rs.json['relays']):
        relay['stability_is_overloaded'] = i < 2  # 2 of 4 overloaded
    return rs


def _args(relay_set, page_key):
    value, group = next(iter(relay_set.json['sorted'][page_key].items()))
    return build_template_args(relay_set, page_key, value, group, [], set())


@pytest.mark.parametrize('page_key', ['contact', 'family', 'as'])
def test_build_template_args_includes_overload_summary(relay_set, page_key):
    assert _args(relay_set, page_key)['overload_summary'] == {
        'overloaded': 2, 'total': 4, 'pct_formatted': '50.0%'}


def test_build_template_args_skips_out_of_scope_pages(relay_set):
    """Country pages must not get an overload_summary (out of requested scope)."""
    assert _args(relay_set, 'country')['overload_summary'] is None


def test_build_template_args_hides_when_zero_overloaded(relay_set):
    saved = [r['stability_is_overloaded'] for r in relay_set.json['relays']]
    try:
        for r in relay_set.json['relays']:
            r['stability_is_overloaded'] = False
        assert _args(relay_set, 'contact')['overload_summary'] is None
    finally:
        for r, flag in zip(relay_set.json['relays'], saved):
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


def test_detail_summary_hides_overload_when_none(jinja_env):
    assert 'Overloaded' not in _render_detail_summary(jinja_env)


def test_overload_bullet_macro_singular(jinja_env):
    rendered = jinja_env.from_string(
        "{% from 'macros.html' import overload_bullet %}{{ overload_bullet(summary) }}"
    ).render(summary={'overloaded': 1, 'total': 1, 'pct_formatted': '100.0%'})
    assert '100.0% (1 of 1 relay)' in rendered
    assert '1 relays' not in rendered


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
