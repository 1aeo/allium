"""Template render tests for the Overloaded summary bullet."""

import pytest


SAMPLE_SUMMARY = {
    'overloaded': 2,
    'total': 10,
    'pct_formatted': '20.0%',
}

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


def _render_detail_summary(jinja_env, overload_summary=None, exit_dns_health_summary=None):
    template = jinja_env.from_string(DETAIL_SUMMARY_CALL)
    return template.render(
        overload_summary=overload_summary,
        exit_dns_health_summary=exit_dns_health_summary,
        base_url=None,
        validated_aroi_domains=set(),
    )


def test_detail_summary_shows_overload_bullet(jinja_env):
    rendered = _render_detail_summary(jinja_env, overload_summary=SAMPLE_SUMMARY)
    assert 'Overloaded' in rendered
    assert '20.0% (2 of 10 relays)' in rendered
    assert 'al-status-danger' in rendered


def test_detail_summary_hides_overload_when_none(jinja_env):
    rendered = _render_detail_summary(jinja_env, overload_summary=None)
    assert 'Overloaded' not in rendered


def test_detail_summary_places_overload_before_dns(jinja_env):
    dns = {
        'exit_count': 3,
        'healthy': 3,
        'failing': 0,
        'untested': 0,
        'healthy_pct': 100,
        'failing_pct': 0,
        'untested_pct': 0,
    }
    rendered = _render_detail_summary(
        jinja_env,
        overload_summary=SAMPLE_SUMMARY,
        exit_dns_health_summary=dns,
    )
    assert rendered.index('Overloaded') < rendered.index('Exit DNS Health')


def test_overload_bullet_macro_singular(jinja_env):
    template = jinja_env.from_string(
        "{% from 'macros.html' import overload_bullet %}"
        "{{ overload_bullet(summary) }}"
    )
    rendered = template.render(summary={
        'overloaded': 1,
        'total': 1,
        'pct_formatted': '100.0%',
    })
    assert '100.0% (1 of 1 relay)' in rendered
    assert 'relays' not in rendered.split('of 1 ')[1][:10]


def _contact_context(overload_summary=None):
    relay = {
        'aroi_domain': 'example.org',
        'country': 'us',
        'country_name': 'United States',
        'observed_bandwidth': 1000000,
        'nickname': 'TestRelay',
        'fingerprint': 'ABC123DEF456',
        'running': True,
        'flags': ['Running', 'Valid'],
        'flags_escaped': ['Running', 'Valid'],
        'flags_lower_escaped': ['running', 'valid'],
        'effective_family': [],
        'measured': True,
        'uptime_display': 'UP 5d 12h',
        'uptime_api_display': '99.5%',
        'or_addresses': ['192.168.1.1:9001'],
        'as': 'AS7922',
        'as_name': 'Comcast Cable',
        'platform': 'Linux',
        'first_seen': '2023-01-01 12:00:00',
        'first_seen_date_escaped': '2023-01-01',
        'contact_md5': 'abcd1234',
        'contact': 'test@example.com',
    }
    return {
        'contact': 'test@example.com',
        'contact_hash': 'abcd1234',
        'bandwidth': '150.0',
        'bandwidth_unit': 'MB/s',
        'consensus_weight_fraction': 0.025,
        'network_position': {
            'label': 'mixed',
            'formatted_string': 'Mixed (5 total relays)',
        },
        'relay_subset': [relay],
        'relays': {'json': {'relay_subset': [relay]}, 'use_bits': False},
        'page_ctx': {'path_prefix': '../'},
        'contact_display_data': {
            'bandwidth_breakdown': '50.0 MB/s guard',
            'consensus_weight_breakdown': '1.0% guard',
            'operator_intelligence': {},
        },
        'contact_rankings': [],
        'operator_reliability': None,
        'contact_validation_status': None,
        'aroi_validation_timestamp': None,
        'is_validated_aroi': False,
        'primary_country_data': None,
        'exit_dns_health_summary': {
            'exit_count': 2,
            'healthy': 2,
            'failing': 0,
            'untested': 0,
            'healthy_pct': 100,
            'failing_pct': 0,
            'untested_pct': 0,
        },
        'overload_summary': overload_summary,
        'guard_count': 1,
        'middle_count': 1,
        'exit_count': 1,
        'base_url': None,
        'validated_aroi_domains': set(),
        'sortable_scope': 'none',
        'contact_sort_mode': None,
        'contact_sort_links': {},
        'contact_sort_enabled': False,
        'contact_has_ipv6': False,
    }


def test_contact_html_shows_overload_before_dns(jinja_env):
    template = jinja_env.get_template('contact.html')
    rendered = template.render(**_contact_context(SAMPLE_SUMMARY))
    assert 'Overloaded' in rendered
    assert '20.0% (2 of 10 relays)' in rendered
    assert rendered.index('Overloaded') < rendered.index('Exit DNS Health')


def test_contact_html_hides_overload_when_none(jinja_env):
    template = jinja_env.get_template('contact.html')
    rendered = template.render(**_contact_context(None))
    assert 'Overloaded' not in rendered
