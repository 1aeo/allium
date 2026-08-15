"""Tests for current-only overload status (no Onionoo history series)."""
from datetime import datetime, timezone

from allium.lib.stability_utils import current_overload_status

# F3Netze snapshot: last report 2026-08-13 05:00 UTC, published 2026-08-15 06:00.
F3_TS_MS = 1786597200000
PUBLISHED = datetime(2026, 8, 15, 6, 0, tzinfo=timezone.utc).timestamp()


def test_no_fields_means_not_overloaded():
    assert current_overload_status({}, PUBLISHED) is None
    assert current_overload_status({'nickname': 'th4r'}, PUBLISHED) is None


def test_general_active_within_72h():
    status = current_overload_status(
        {'overload_general_timestamp': F3_TS_MS}, PUBLISHED)
    assert status is not None
    assert status['active'] is True
    assert status['reasons'] == ['general']
    assert status['last_report'] == datetime(2026, 8, 13, 5, 0, tzinfo=timezone.utc)
    assert 'OVERLOADED NOW' in status['label']
    assert '13 Aug 05:00 UTC' in status['label']


def test_stale_general_is_not_current():
    # 80 hours before published — outside the proposal-328 window.
    stale_ms = int((PUBLISHED - 80 * 3600) * 1000)
    assert current_overload_status(
        {'overload_general_timestamp': stale_ms}, PUBLISHED) is None


def test_rate_limit_hit_is_current_without_general():
    status = current_overload_status({
        'overload_ratelimits': {
            'timestamp': F3_TS_MS,
            'rate-limit': 1000,
            'burst-limit': 2000,
            'write-count': 2,
            'read-count': 0,
        },
    }, PUBLISHED)
    assert status is not None
    assert status['reasons'] == ['rate-limit']


def test_rate_limit_present_but_not_hit():
    assert current_overload_status({
        'overload_ratelimits': {
            'timestamp': F3_TS_MS,
            'rate-limit': 1000,
            'burst-limit': 2000,
            'write-count': 0,
            'read-count': 0,
        },
    }, PUBLISHED) is None


def test_fd_exhausted_is_current():
    status = current_overload_status({
        'overload_fd_exhausted': {'timestamp': F3_TS_MS},
    }, PUBLISHED)
    assert status is not None
    assert status['reasons'] == ['fd']
