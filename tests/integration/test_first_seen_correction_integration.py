"""
Integration test for first_seen correction end-to-end through Relays().

The 1aeo snapshot at ``docs/development/example-data/1aeo_relays_data.json``
predates the regression and shows *correct* 2025-dated first_seen values, so
we synthesise the buggy state on top of it: pick a few relays, save their
true first_seen, overwrite with a reset date, build matching uptime data,
run the correction, and verify both the raw correction AND the downstream
Relays() categorisation see the corrected values.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from allium.lib.first_seen_correction import correct_first_seen
from allium.lib.relays import Relays
from allium.lib.time_utils import parse_onionoo_timestamp


pytestmark = [pytest.mark.integration]


FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / 'docs' / 'development' / 'example-data' / '1aeo_relays_data.json'
)


def _load_fixture():
    with open(FIXTURE_PATH, 'r') as f:
        return json.load(f)


def _floor_to_grid(dt, interval_seconds):
    """Floor a UTC datetime to the nearest interval-aligned boundary.

    Mirrors onionoo's own bucket alignment: the ``first`` timestamp of a
    period is always a multiple of the period's interval relative to the
    epoch.
    """
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    elapsed = int((dt - epoch).total_seconds())
    floored = (elapsed // interval_seconds) * interval_seconds
    return epoch + timedelta(seconds=floored)


def test_correction_propagates_to_relays_sorted_categories():
    """Synthesise buggy state on 1aeo fixture; verify correction + categorisation."""
    fixture = _load_fixture()
    relays = list(fixture.get('relays', []))
    assert len(relays) >= 5, 'fixture must contain at least 5 relays'

    # Use the first 5 relays for our buggy-state synthesis.
    affected = relays[:5]
    reset_date = '2026-05-01 00:00:00'

    # For each, save the true first_seen and overwrite with the reset date.
    true_first_seen = {}
    for relay in affected:
        fp = relay['fingerprint']
        true_first_seen[fp] = relay['first_seen']
        relay['first_seen'] = reset_date

    # Build a synthetic uptime payload covering only the 5 affected relays.
    # Each relay's 5_years.first is the true first_seen floored to the 10-day
    # grid (864000s = 10d, onionoo's actual 5_years interval), with a single
    # non-null value at index 0.
    #
    # The correction module returns the MIDPOINT of the earliest non-null
    # interval (= `first` itself, when first non-null is at idx 0). This
    # matches onionoo's documented point estimate for when the observation
    # occurred.
    interval = 864000
    uptime_relays = []
    expected_corrected = {}
    for fp, true_str in true_first_seen.items():
        true_dt = parse_onionoo_timestamp(true_str)
        assert true_dt is not None
        first_dt = _floor_to_grid(true_dt, interval)
        first_str = first_dt.strftime('%Y-%m-%d %H:%M:%S')
        # idx=0 -> midpoint = first.
        expected_corrected[fp] = first_str
        # Synthesise only the 5_years period for this test -- in real onionoo
        # data, shorter periods (1_year, 6_months, 1_month) only span the
        # last N units relative to today, so their values would be all-None
        # for any portion before the relay's true first_seen. Modeling that
        # accurately is unnecessary noise for this test; the 5_years bucket
        # is the one that actually provides the older signal in practice.
        uptime_relays.append({
            'fingerprint': fp,
            'uptime': {
                '5_years': {
                    'first': first_str,
                    'last': '2026-05-13 00:00:00',
                    'interval': interval,
                    'count': 43,
                    'values': [999] * 43,
                },
            },
        })

    uptime_data = {
        'version': '8.0',
        'relays_published': '2026-05-13 12:00:00',
        'relays': uptime_relays,
    }

    relay_data = {
        'version': fixture.get('version', '8.0'),
        'relays_published': '2026-05-13 12:00:00',
        'relays': relays,
    }

    # ----- 1. Apply the correction. -----
    correct_first_seen(relay_data, uptime_data)

    # ----- 2. Verify raw-data correction. -----
    summary = relay_data['_first_seen_correction_summary']
    # 5 affected relays should be corrected; the remaining 648 lack
    # uptime entries so they fall under missing_uptime.
    assert summary['corrected'] == 5
    assert summary['missing_uptime'] == len(relays) - 5
    assert summary['total'] == len(relays)

    for relay in affected:
        fp = relay['fingerprint']
        # first_seen now equals the floored true value.
        assert relay['first_seen'] == expected_corrected[fp], (
            'fingerprint {}: expected {}, got {}'.format(
                fp, expected_corrected[fp], relay['first_seen']
            )
        )
        # original preserved.
        assert relay['first_seen_onionoo_raw'] == reset_date
        # metadata.
        assert relay['_first_seen_corrected'] is True
        assert relay['_first_seen_correction_source'] == 'onionoo_uptime'
        # Corrected value is the midpoint of interval 0 = `first`, which
        # is at most one interval (10 days) earlier than the true value
        # due to grid-flooring. So corrected is in [true - interval, true].
        corrected = parse_onionoo_timestamp(relay['first_seen'])
        true_dt = parse_onionoo_timestamp(true_first_seen[fp])
        assert corrected <= true_dt
        max_gap = timedelta(seconds=interval)
        assert (true_dt - corrected) <= max_gap, (
            'fingerprint {}: gap {} exceeds max {} (true={}, corrected={})'.format(
                fp, true_dt - corrected, max_gap, true_dt, corrected
            )
        )

    # ----- 3. Construct Relays() with the corrected data; check categorisation. -----
    with tempfile.TemporaryDirectory() as tmpdir:
        relay_set = Relays(
            output_dir=tmpdir,
            onionoo_url='http://localhost',
            relay_data=relay_data,
            progress=False,
        )

    assert relay_set.json is not None, 'Relays() returned None unexpectedly'

    sorted_first_seen = relay_set.json['sorted']['first_seen']

    # The reset-date bucket must NOT contain all 5 affected relays (some may
    # legitimately match on date if the floor lands on 2026-05-01, but that's
    # unlikely for our 1aeo fixture which has 2025-* original dates).
    reset_date_only = reset_date.split(' ')[0]
    affected_fps = {r['fingerprint'] for r in affected}
    relays_in_reset_bucket = set()
    if reset_date_only in sorted_first_seen:
        # categorization stores 'relays' as list of indices; resolve them.
        idx_list = sorted_first_seen[reset_date_only].get('relays', [])
        for idx in idx_list:
            relays_in_reset_bucket.add(relay_set.json['relays'][idx]['fingerprint'])
    overlap = affected_fps & relays_in_reset_bucket
    assert overlap == set(), (
        'affected relays should NOT be in the 2026-05-01 bucket; overlap={}'.format(overlap)
    )

    # Each affected relay's corrected first_seen date should appear as a bucket.
    for relay in affected:
        date_part = relay['first_seen'].split(' ')[0]
        assert date_part in sorted_first_seen, (
            'corrected date {} missing from sorted[\'first_seen\']'.format(date_part)
        )


def test_coordinator_exposes_first_seen_repair_stats_on_relay_set():
    """Verify the coordinator's relay_set.first_seen_repair_stats is wired."""
    # We don't drive the whole coordinator (it does real HTTP); instead we
    # mimic the wiring: call correct_first_seen, then construct Relays,
    # then verify the attribute can be set the same way coordinator does it.
    fixture = _load_fixture()
    relay_data = {
        'version': fixture.get('version', '8.0'),
        'relays_published': '2026-05-13 12:00:00',
        'relays': list(fixture['relays'])[:3],
    }
    uptime_data = {'relays': []}

    correct_first_seen(relay_data, uptime_data)

    with tempfile.TemporaryDirectory() as tmpdir:
        relay_set = Relays(
            output_dir=tmpdir,
            onionoo_url='http://localhost',
            relay_data=relay_data,
            progress=False,
        )

    # Coordinator does: relay_set.first_seen_repair_stats = relay_data.get(...)
    relay_set.first_seen_repair_stats = relay_data.get('_first_seen_correction_summary')

    assert relay_set.first_seen_repair_stats is not None
    assert relay_set.first_seen_repair_stats['total'] == 3
    assert relay_set.first_seen_repair_stats['missing_uptime'] == 3
    assert relay_set.first_seen_repair_stats['corrected'] == 0


def test_coordinator_create_relay_set_invokes_correction():
    """End-to-end through Coordinator.create_relay_set without real HTTP.

    Drives the full coordinator code path that wires correct_first_seen,
    using a mocked worker_data dict for uptime. The downstream
    `enrich_with_api_data` (network-health metrics, AROI leaderboards, etc.)
    is patched to a no-op because building synthetic data complete enough
    for it would not exercise anything additional that our other tests
    don't already cover.

    Verifies:
    - correct_first_seen is invoked (relay's first_seen is repaired)
    - relay_set.first_seen_repair_stats is set
    - sorted['first_seen'] bucket reflects the corrected date
    """
    from unittest.mock import patch
    from allium.lib.coordinator import Coordinator

    fp = '0040E1791755D340BA8109F4C1849666582CF56C'
    relay_data = {
        'version': '8.0',
        'relays_published': '2026-05-13 12:00:00',
        'relays': [
            {
                'fingerprint': fp,
                'nickname': 'testrelay',
                'first_seen': '2026-04-06 23:00:00',
                'last_seen': '2026-05-13 12:00:00',
                'running': True,
                'flags': ['Running', 'Valid'],
                'or_addresses': ['10.0.0.1:9001'],
                'observed_bandwidth': 100000,
                'consensus_weight': 100,
                'country': 'us',
                'country_name': 'United States',
            },
        ],
    }
    uptime_data = {
        'version': '8.0',
        'relays': [
            {
                'fingerprint': fp,
                'uptime': {
                    '5_years': {
                        'first': '2025-03-08 00:00:00',
                        'last': '2026-05-13 00:00:00',
                        'interval': 864000,
                        'count': 43,
                        'values': [999] * 43,
                    },
                },
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        coord = Coordinator(output_dir=tmpdir, progress=False)
        coord.worker_data = {'onionoo_uptime': uptime_data}
        # Patch enrich_with_api_data to a no-op; building synthetic data
        # complete enough for it would not exercise additional behaviour
        # that our other tests don't cover.
        with patch(
            'allium.lib.relays.Relays.enrich_with_api_data',
            return_value=None,
        ):
            relay_set = coord.create_relay_set(relay_data)

    assert relay_set is not None
    assert relay_set.first_seen_repair_stats['corrected'] == 1
    assert relay_set.first_seen_repair_stats['total'] == 1

    relay = relay_set.json['relays'][0]
    # Midpoint at idx=0 == `first` == 2025-03-08.
    assert relay['first_seen'] == '2025-03-08 00:00:00'
    assert relay['first_seen_onionoo_raw'] == '2026-04-06 23:00:00'
    assert relay['_first_seen_corrected'] is True

    assert '2025-03-08' in relay_set.json['sorted']['first_seen']
    assert '2026-04-06' not in relay_set.json['sorted']['first_seen']


def test_corrected_first_seen_flows_into_network_health_metrics():
    """Direct proof that network-health counters consume corrected dates.

    Builds two relays:
    - relay A: buggy `first_seen` (5 days ago) + uptime showing 18mo old
    - relay B: legitimate new relay (no correction)

    Asserts that after correction + network-health computation:
    - new_relays_30d counts only relay B (1), not both
    - new_relays_1y counts only relay B (1), not both
    - network_mean_age_formatted reflects the corrected (older) date
    """
    from datetime import datetime, timedelta, timezone
    from allium.lib.first_seen_correction import correct_first_seen
    from allium.lib.relays import Relays

    now = datetime.now(tz=timezone.utc)
    five_days_ago = now - timedelta(days=5)
    eighteen_months_ago = now - timedelta(days=18 * 30)

    fp_a = 'AAAA' + 'A' * 36
    fp_b = 'BBBB' + 'B' * 36

    # Relay A: buggy reset state -- /details says new, /uptime says old.
    # Relay B: legitimately new.
    relay_a = {
        'fingerprint': fp_a, 'nickname': 'oldrelay',
        'first_seen': five_days_ago.strftime('%Y-%m-%d %H:%M:%S'),
        'last_seen': now.strftime('%Y-%m-%d %H:%M:%S'),
        'running': True, 'flags': ['Running', 'Valid', 'Stable'],
        'or_addresses': ['10.0.0.1:9001'],
        'observed_bandwidth': 100000, 'consensus_weight': 100,
        'country': 'us', 'country_name': 'United States',
        'platform': 'Tor 0.4.8.10 on Linux',
    }
    relay_b = {
        'fingerprint': fp_b, 'nickname': 'newrelay',
        'first_seen': five_days_ago.strftime('%Y-%m-%d %H:%M:%S'),
        'last_seen': now.strftime('%Y-%m-%d %H:%M:%S'),
        'running': True, 'flags': ['Running', 'Valid'],
        'or_addresses': ['10.0.0.2:9001'],
        'observed_bandwidth': 50000, 'consensus_weight': 50,
        'country': 'us', 'country_name': 'United States',
        'platform': 'Tor 0.4.8.10 on Linux',
    }
    relay_data = {
        'version': '8.0',
        'relays_published': now.strftime('%Y-%m-%d %H:%M:%S'),
        'relays': [relay_a, relay_b],
    }

    # Uptime: A is 18mo old in uptime history, B is genuinely new (no uptime
    # entry -- "missing_uptime" path; no correction applied).
    uptime_data = {
        'relays': [
            {
                'fingerprint': fp_a,
                'uptime': {
                    '5_years': {
                        'first': eighteen_months_ago.strftime('%Y-%m-%d %H:%M:%S'),
                        'last': now.strftime('%Y-%m-%d %H:%M:%S'),
                        'interval': 864000,
                        'count': 55,
                        'values': [999] * 55,
                    },
                },
            },
        ],
    }

    correct_first_seen(relay_data, uptime_data)

    # Sanity: A was corrected to ~18mo old, B was left as-is.
    assert relay_a['_first_seen_corrected'] is True
    assert '_first_seen_corrected' not in relay_b

    with tempfile.TemporaryDirectory() as tmpdir:
        relay_set = Relays(
            output_dir=tmpdir, onionoo_url='http://localhost',
            relay_data=relay_data, progress=False,
        )
        relay_set._calculate_network_health_metrics()

    health = relay_set.json['network_health']

    # With correction, only relay B (genuinely new) should be counted.
    assert health['new_relays_30d'] == 1, (
        'expected only 1 new relay in 30d (relay B); got {}; relay_a first_seen={}, '
        'relay_b first_seen={}'.format(health['new_relays_30d'],
                                       relay_a['first_seen'], relay_b['first_seen'])
    )
    assert health['new_relays_1y'] == 1, (
        'expected only 1 new relay in 1y (relay B); got {}'.format(health['new_relays_1y'])
    )

    # Mean age should reflect the corrected (older) A: mean of ~5d and ~18mo.
    mean_str = health.get('network_mean_age_formatted', '')
    assert mean_str and 'Unknown' not in mean_str
    # Loosely: at least 2 months old on average (one ~5d relay, one ~18mo
    # relay -> mean ~9mo). Without correction it would be ~5d for both.
    assert ('m' in mean_str or 'mo' in mean_str or 'y' in mean_str), (
        'mean age {} does not include months/years -- correction may not have '
        'propagated to network_health'.format(mean_str)
    )


def test_coordinator_create_relay_set_no_uptime_is_silent_noop():
    """When --apis details (no uptime), correct_first_seen short-circuits."""
    from unittest.mock import patch
    from allium.lib.coordinator import Coordinator

    fp = '0040E1791755D340BA8109F4C1849666582CF56C'
    relay_data = {
        'version': '8.0',
        'relays_published': '2026-05-13 12:00:00',
        'relays': [
            {
                'fingerprint': fp,
                'nickname': 'testrelay',
                'first_seen': '2026-04-06 23:00:00',
                'last_seen': '2026-05-13 12:00:00',
                'running': True,
                'flags': ['Running', 'Valid'],
                'or_addresses': ['10.0.0.1:9001'],
                'observed_bandwidth': 100000,
                'consensus_weight': 100,
                'country': 'us',
                'country_name': 'United States',
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        coord = Coordinator(output_dir=tmpdir, progress=False)
        coord.worker_data = {}  # no uptime
        with patch(
            'allium.lib.relays.Relays.enrich_with_api_data',
            return_value=None,
        ):
            relay_set = coord.create_relay_set(relay_data)

    assert relay_set is not None
    assert relay_set.first_seen_repair_stats['corrected'] == 0
    assert relay_set.first_seen_repair_stats['missing_uptime'] == 1
    assert relay_set.json['relays'][0]['first_seen'] == '2026-04-06 23:00:00'
    assert 'first_seen_onionoo_raw' not in relay_set.json['relays'][0]
