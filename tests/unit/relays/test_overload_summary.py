"""Unit tests for group-level overload summary aggregation."""

import pytest

from allium.lib.stability_utils import compute_group_overload_summary
from allium.lib.page_writer import build_template_args


def test_empty_members_returns_none():
    assert compute_group_overload_summary([]) is None


def test_zero_overloaded_returns_none():
    members = [
        {'stability_is_overloaded': False},
        {'stability_is_overloaded': False},
        {},  # missing key treated as not overloaded
    ]
    assert compute_group_overload_summary(members) is None


def test_mixed_overloaded_counts():
    members = (
        [{'stability_is_overloaded': True}] * 3
        + [{'stability_is_overloaded': False}] * 5
    )
    summary = compute_group_overload_summary(members)
    assert summary is not None
    assert summary['overloaded'] == 3
    assert summary['total'] == 8
    assert summary['pct_formatted'] == '37.5%'
    assert 'pct' not in summary


def test_all_overloaded():
    members = [{'stability_is_overloaded': True} for _ in range(4)]
    summary = compute_group_overload_summary(members)
    assert summary['overloaded'] == 4
    assert summary['total'] == 4
    assert summary['pct_formatted'] == '100.0%'


def test_tiny_fraction_uses_floor():
    """1 of 3000 would round to 0.0% — must show <0.1% instead."""
    members = [{'stability_is_overloaded': True}] + [
        {'stability_is_overloaded': False} for _ in range(2999)
    ]
    summary = compute_group_overload_summary(members)
    assert summary['overloaded'] == 1
    assert summary['total'] == 3000
    assert summary['pct_formatted'] == '<0.1%'


def test_missing_flag_treated_as_not_overloaded():
    members = [
        {'stability_is_overloaded': True},
        {},
        {'nickname': 'no-flag'},
    ]
    summary = compute_group_overload_summary(members)
    assert summary['overloaded'] == 1
    assert summary['total'] == 3
    assert summary['pct_formatted'] == '33.3%'


def _make_minimal_relay_set(tmp_path, overloaded_flags):
    """Build a Relays instance with one contact/family/as group of given overload flags."""
    from allium.lib.relays import Relays

    relays = []
    for i, is_overloaded in enumerate(overloaded_flags):
        relays.append({
            'nickname': f'Relay{i}',
            'fingerprint': f'{i:040d}',
            'running': True,
            'flags': ['Running', 'Valid'],
            'observed_bandwidth': 1_000_000,
            'consensus_weight': 100,
            'consensus_weight_fraction': 0.01,
            'or_addresses': [f'192.0.2.{i + 1}:9001'],
            'as': 'AS64500',
            'as_name': 'Test AS',
            'country': 'us',
            'country_name': 'United States',
            'platform': 'Linux',
            'first_seen': '2023-01-01 00:00:00',
            'last_seen': '2026-07-12 00:00:00',
            'contact': 'ops@example.com',
            'effective_family': [f'{j:040d}' for j in range(len(overloaded_flags))],
            'measured': True,
            'stability_is_overloaded': is_overloaded,
        })

    relay_set = Relays(
        output_dir=str(tmp_path),
        onionoo_url='https://test.example.com',
        relay_data={'relays': relays},
        use_bits=False,
        progress=False,
        mp_workers=0,
    )
    # Relays.__init__ reprocesses members; re-apply flags after categorization
    # since stability is normally set during bandwidth enrichment.
    for relay, flag in zip(relay_set.json['relays'], overloaded_flags):
        relay['stability_is_overloaded'] = flag
    return relay_set


@pytest.mark.parametrize('page_key', ['contact', 'family', 'as'])
def test_build_template_args_includes_overload_summary(tmp_path, page_key):
    relay_set = _make_minimal_relay_set(tmp_path, [True, True, False, False])
    sorted_groups = relay_set.json['sorted'][page_key]
    assert sorted_groups, f'expected sorted groups for {page_key}'
    value = next(iter(sorted_groups))
    group = sorted_groups[value]

    args = build_template_args(relay_set, page_key, value, group, [], set())
    summary = args['overload_summary']
    assert summary is not None
    assert summary['overloaded'] == 2
    assert summary['total'] == 4
    assert summary['pct_formatted'] == '50.0%'


def test_build_template_args_hides_when_zero_overloaded(tmp_path):
    relay_set = _make_minimal_relay_set(tmp_path, [False, False])
    contact_hash = next(iter(relay_set.json['sorted']['contact']))
    group = relay_set.json['sorted']['contact'][contact_hash]
    args = build_template_args(relay_set, 'contact', contact_hash, group, [], set())
    assert args['overload_summary'] is None


def test_build_template_args_skips_out_of_scope_pages(tmp_path):
    """Country pages must not get an overload_summary (out of requested scope)."""
    relay_set = _make_minimal_relay_set(tmp_path, [True, False])
    country = next(iter(relay_set.json['sorted']['country']))
    group = relay_set.json['sorted']['country'][country]
    args = build_template_args(relay_set, 'country', country, group, [], set())
    assert args['overload_summary'] is None
