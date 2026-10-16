"""
Unit tests for allium.lib.first_seen_correction.

Each test is small and focused. The module documentation in
allium/lib/first_seen_correction.py explains the design rules; these tests
codify them.
"""

import logging
import re

import pytest

from allium.lib.first_seen_correction import (
    FIRST_SEEN_FLOOR,
    _earliest_uptime_interval,
    correct_first_seen,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FP = '0040E1791755D340BA8109F4C1849666582CF56C'


def _make_uptime(fingerprint=FP, periods=None):
    """Build a minimal valid onionoo /uptime response.

    ``periods`` is a dict of period name -> {first, interval, values, ...}.
    """
    if periods is None:
        periods = {}
    return {
        'version': '8.0',
        'relays_published': '2026-05-13 12:00:00',
        'relays': [
            {
                'fingerprint': fingerprint,
                'uptime': periods,
            },
        ],
    }


def _make_relay(first_seen='2026-04-06 23:00:00', fingerprint=FP):
    return {
        'fingerprint': fingerprint,
        'first_seen': first_seen,
        'nickname': 'test',
    }


def _make_relay_data(*relays):
    return {'relays': list(relays)}


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------

def test_corrects_when_uptime_predates_first_seen():
    relay = _make_relay(first_seen='2026-04-06 23:00:00')
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2025-03-08 00:00:00',
            'last': '2026-05-02 00:00:00',
            'interval': 864000,
            'count': 43,
            'values': [999] * 43,
        },
    })
    data = _make_relay_data(relay)

    correct_first_seen(data, uptime)

    # Per onionoo spec, `first` is the midpoint of interval 0 -- onionoo's
    # documented point estimate for when the observation occurred. Allium
    # displays first_seen as an exact date, so we use the midpoint rather
    # than the lower bound that would predate the relay's existence.
    assert relay['first_seen'] == '2025-03-08 00:00:00'
    assert relay['first_seen_onionoo_raw'] == '2026-04-06 23:00:00'
    assert relay['_first_seen_corrected'] is True
    assert relay['_first_seen_correction_source'] == 'onionoo_uptime'
    summary = data['_first_seen_correction_summary']
    assert summary['corrected'] == 1
    assert summary['total'] == 1


# ---------------------------------------------------------------------------
# 2-4. No-op short-circuits
# ---------------------------------------------------------------------------

def test_no_change_when_uptime_data_missing():
    relay = _make_relay()
    data = _make_relay_data(relay)
    correct_first_seen(data, None)
    assert relay['first_seen'] == '2026-04-06 23:00:00'
    assert 'first_seen_onionoo_raw' not in relay
    assert '_first_seen_corrected' not in relay
    # Summary still stamped so callers (api_diagnostics) don't have to None-check.
    assert data['_first_seen_correction_summary']['corrected'] == 0
    assert data['_first_seen_correction_summary']['missing_uptime'] == 1


def test_no_change_when_uptime_data_has_no_relays():
    relay = _make_relay()
    data = _make_relay_data(relay)
    correct_first_seen(data, {'relays': []})
    assert relay['first_seen'] == '2026-04-06 23:00:00'
    assert 'first_seen_onionoo_raw' not in relay
    assert data['_first_seen_correction_summary']['missing_uptime'] == 1


def test_no_change_when_relay_data_has_no_relays():
    data = {'relays': []}
    correct_first_seen(data, _make_uptime())
    assert data['relays'] == []
    summary = data['_first_seen_correction_summary']
    assert summary['total'] == 0
    assert summary['corrected'] == 0


def test_empty_relays_branch_emits_summary_log():
    """Docstring promises the no-corrections branches also log in progress
    mode. Lock that contract in for the empty-relays branch (other branches
    are covered by test_progress_logger_called_once_with_summary)."""
    captured = []
    correct_first_seen(
        {'relays': []},
        _make_uptime(),
        progress_logger=lambda msg: captured.append(msg),
    )
    assert len(captured) == 1
    assert '0/0' in captured[0]


# ---------------------------------------------------------------------------
# 5. Fingerprint missing from uptime
# ---------------------------------------------------------------------------

def test_no_change_when_fingerprint_not_in_uptime():
    relay = _make_relay(fingerprint='AAAA' + 'B' * 36)
    uptime = _make_uptime(  # different fingerprint
        fingerprint='CCCC' + 'D' * 36,
        periods={
            '5_years': {
                'first': '2020-01-01 00:00:00',
                'interval': 864000,
                'values': [999],
            },
        },
    )
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    assert relay['first_seen'] == '2026-04-06 23:00:00'
    assert 'first_seen_onionoo_raw' not in relay
    assert data['_first_seen_correction_summary']['missing_uptime'] == 1


# ---------------------------------------------------------------------------
# 6. Uptime starts AFTER first_seen
# ---------------------------------------------------------------------------

def test_no_change_when_uptime_starts_after_first_seen():
    relay = _make_relay(first_seen='2025-01-01 00:00:00')
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2025-01-03 00:00:00',  # 2 days AFTER first_seen
            'interval': 864000,
            'values': [999, 999, 999],
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    assert relay['first_seen'] == '2025-01-01 00:00:00'
    assert 'first_seen_onionoo_raw' not in relay
    assert data['_first_seen_correction_summary']['unchanged'] == 1


# ---------------------------------------------------------------------------
# 7. Leading nulls in uptime values
# ---------------------------------------------------------------------------

def test_uses_first_non_null_index_when_leading_nulls():
    relay = _make_relay(first_seen='2026-04-06 23:00:00')
    # 3 leading Nones, then 999. Interval=864000s = 10 days.
    # first=2025-03-08 (midpoint of interval 0), idx=3 -> midpoint of interval 3
    # is 2025-03-08 + 30 days = 2025-04-07.
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2025-03-08 00:00:00',
            'interval': 864000,
            'values': [None, None, None, 999, 999],
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    assert relay['first_seen'] == '2025-04-07 00:00:00'


# ---------------------------------------------------------------------------
# 8. Zero is a valid observation
# ---------------------------------------------------------------------------

def test_zero_value_counts_as_observation():
    relay = _make_relay(first_seen='2026-04-06 23:00:00')
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2025-03-08 00:00:00',
            'interval': 864000,
            'values': [None, None, 0, 999],   # 0 = tracked-but-down, valid signal
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    # Should use idx=2 (the 0), not idx=3.
    # Midpoint of interval 2 = 2025-03-08 + 20 days = 2025-03-28.
    assert relay['first_seen'] == '2025-03-28 00:00:00'


# ---------------------------------------------------------------------------
# 9. MIN across multiple periods
# ---------------------------------------------------------------------------

def test_picks_earliest_across_multiple_periods():
    relay = _make_relay(first_seen='2026-04-06 23:00:00')
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2024-01-01 00:00:00',
            'interval': 864000,
            'values': [None, None, None, None, None, 999],  # idx=5 -> 2024-02-20
        },
        '1_year': {
            'first': '2025-05-13 00:00:00',
            'interval': 172800,
            'values': [999],
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    # idx=5 in 5_years bucket: midpoint = 2024-01-01 + 50d = 2024-02-20.
    assert relay['first_seen'] == '2024-02-20 00:00:00'


# ---------------------------------------------------------------------------
# 10. All-None values
# ---------------------------------------------------------------------------

def test_handles_all_null_values():
    relay = _make_relay()
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2025-03-08 00:00:00',
            'interval': 864000,
            'values': [None] * 43,
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    assert relay['first_seen'] == '2026-04-06 23:00:00'
    assert 'first_seen_onionoo_raw' not in relay
    assert data['_first_seen_correction_summary']['no_signal'] == 1


# ---------------------------------------------------------------------------
# 11. Empty uptime dict
# ---------------------------------------------------------------------------

def test_handles_empty_uptime_dict():
    relay = _make_relay()
    uptime = _make_uptime(periods={})  # no periods at all
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    assert relay['first_seen'] == '2026-04-06 23:00:00'
    assert data['_first_seen_correction_summary']['no_signal'] == 1


# ---------------------------------------------------------------------------
# 12. Malformed period (missing interval)
# ---------------------------------------------------------------------------

def test_handles_malformed_period_missing_interval():
    relay = _make_relay(first_seen='2026-04-06 23:00:00')
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2024-01-01 00:00:00',
            # no interval
            'values': [999],
        },
        '1_year': {
            'first': '2025-05-13 00:00:00',
            'interval': 172800,
            'values': [999],
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    # 5_years skipped (no interval), 1_year used: midpoint at idx=0 is
    # exactly `first` = 2025-05-13.
    assert relay['first_seen'] == '2025-05-13 00:00:00'


# ---------------------------------------------------------------------------
# 13. Malformed period (unparseable first)
# ---------------------------------------------------------------------------

def test_handles_malformed_period_unparseable_first():
    relay = _make_relay(first_seen='2026-04-06 23:00:00')
    uptime = _make_uptime(periods={
        '5_years': {
            'first': 'not a date',
            'interval': 864000,
            'values': [999],
        },
        '1_year': {
            'first': '2025-05-13 00:00:00',
            'interval': 172800,
            'values': [999],
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)  # must not crash
    # 5_years skipped (unparseable `first`), 1_year used: midpoint at idx=0
    # is exactly `first` = 2025-05-13.
    assert relay['first_seen'] == '2025-05-13 00:00:00'


# ---------------------------------------------------------------------------
# 14. Unparseable relay first_seen
# ---------------------------------------------------------------------------

def test_handles_unparseable_first_seen_on_relay():
    relay = _make_relay(first_seen='garbage')
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2025-03-08 00:00:00',
            'interval': 864000,
            'values': [999],
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    # No change because we can't safely compare.
    assert relay['first_seen'] == 'garbage'
    assert 'first_seen_onionoo_raw' not in relay
    assert data['_first_seen_correction_summary']['invalid_first_seen'] == 1


def test_handles_missing_first_seen_on_relay():
    relay = {'fingerprint': FP, 'nickname': 'no_fs'}
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2025-03-08 00:00:00',
            'interval': 864000,
            'values': [999],
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    assert 'first_seen' not in relay
    assert data['_first_seen_correction_summary']['invalid_first_seen'] == 1


# ---------------------------------------------------------------------------
# 15. Defensive floor (2004-01-01)
# ---------------------------------------------------------------------------

def test_rejects_pre_floor_timestamp():
    relay = _make_relay(first_seen='2026-04-06 23:00:00')
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '1970-01-01 00:00:00',  # epoch-zero garbage, cf. issue #40028
            'interval': 864000,
            'values': [999],
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    assert relay['first_seen'] == '2026-04-06 23:00:00'
    assert 'first_seen_onionoo_raw' not in relay
    assert data['_first_seen_correction_summary']['rejected_floor'] == 1


def test_floor_constant_is_2004():
    """Documents the chosen floor value -- changes should be reviewed."""
    from datetime import datetime, timezone
    assert FIRST_SEEN_FLOOR == datetime(2004, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 16. Original value preserved only when changed
# ---------------------------------------------------------------------------

def test_first_seen_onionoo_raw_only_added_when_changed():
    # Two relays: one corrected, one untouched (uptime starts later).
    relay_a = _make_relay(first_seen='2026-04-06 23:00:00',
                          fingerprint='AAAA' + 'A' * 36)
    relay_b = _make_relay(first_seen='2025-01-01 00:00:00',
                          fingerprint='BBBB' + 'B' * 36)
    uptime = {
        'relays': [
            {
                'fingerprint': 'AAAA' + 'A' * 36,
                'uptime': {
                    '5_years': {
                        'first': '2025-03-08 00:00:00',
                        'interval': 864000,
                        'values': [999],
                    },
                },
            },
            {
                'fingerprint': 'BBBB' + 'B' * 36,
                'uptime': {
                    '5_years': {
                        'first': '2025-03-08 00:00:00',  # AFTER B's first_seen
                        'interval': 864000,
                        'values': [999],
                    },
                },
            },
        ],
    }
    data = _make_relay_data(relay_a, relay_b)
    correct_first_seen(data, uptime)

    # A: corrected -> raw preserved.
    # idx=0 with first=2025-03-08 -- midpoint at idx=0 is exactly `first`.
    assert relay_a['first_seen'] == '2025-03-08 00:00:00'
    assert relay_a['first_seen_onionoo_raw'] == '2026-04-06 23:00:00'
    assert relay_a['_first_seen_corrected'] is True

    # B: untouched -> no metadata fields
    assert relay_b['first_seen'] == '2025-01-01 00:00:00'
    assert 'first_seen_onionoo_raw' not in relay_b
    assert '_first_seen_corrected' not in relay_b
    assert '_first_seen_correction_source' not in relay_b


# ---------------------------------------------------------------------------
# 17. Output format exact
# ---------------------------------------------------------------------------

def test_output_format_is_onionoo_standard():
    relay = _make_relay(first_seen='2026-04-06 23:00:00')
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2025-03-08 00:00:00',
            'interval': 864000,
            'values': [999],
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    # No 'T' separator, no timezone suffix, no microseconds.
    assert re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', relay['first_seen'])


# ---------------------------------------------------------------------------
# 18. Summary counters
# ---------------------------------------------------------------------------

def test_summary_counters():
    # 6 relays exercising every counter except total.
    fps = ['{}{}'.format(c, c * 39) for c in 'ABCDEF']

    # Relay A: corrected.
    relay_a = _make_relay(first_seen='2026-04-06 23:00:00', fingerprint=fps[0])
    # Relay B: unchanged-newer.
    relay_b = _make_relay(first_seen='2025-01-01 00:00:00', fingerprint=fps[1])
    # Relay C: missing-uptime (fingerprint absent from uptime).
    relay_c = _make_relay(first_seen='2026-04-06 23:00:00', fingerprint=fps[2])
    # Relay D: no-signal (all None values).
    relay_d = _make_relay(first_seen='2026-04-06 23:00:00', fingerprint=fps[3])
    # Relay E: rejected-floor (epoch zero).
    relay_e = _make_relay(first_seen='2026-04-06 23:00:00', fingerprint=fps[4])
    # Relay F: invalid first_seen.
    relay_f = _make_relay(first_seen='garbage', fingerprint=fps[5])

    uptime = {
        'relays': [
            {'fingerprint': fps[0], 'uptime': {'5_years': {
                'first': '2025-03-08 00:00:00', 'interval': 864000, 'values': [999]}}},
            {'fingerprint': fps[1], 'uptime': {'5_years': {
                'first': '2025-06-01 00:00:00', 'interval': 864000, 'values': [999]}}},
            # fps[2]: omitted -> missing_uptime
            {'fingerprint': fps[3], 'uptime': {'5_years': {
                'first': '2025-03-08 00:00:00', 'interval': 864000, 'values': [None, None]}}},
            {'fingerprint': fps[4], 'uptime': {'5_years': {
                'first': '1970-01-01 00:00:00', 'interval': 864000, 'values': [999]}}},
            {'fingerprint': fps[5], 'uptime': {'5_years': {
                'first': '2025-03-08 00:00:00', 'interval': 864000, 'values': [999]}}},
        ],
    }
    data = _make_relay_data(relay_a, relay_b, relay_c, relay_d, relay_e, relay_f)

    correct_first_seen(data, uptime)

    summary = data['_first_seen_correction_summary']
    assert summary == {
        'total': 6,
        'corrected': 1,
        'unchanged': 1,
        'missing_uptime': 1,
        'no_signal': 1,
        'rejected_floor': 1,
        'invalid_first_seen': 1,
        'non_dict_skipped': 0,
    }
    # The classification counters sum exactly to `total`.
    classified = (summary['corrected'] + summary['unchanged']
                  + summary['missing_uptime'] + summary['no_signal']
                  + summary['rejected_floor'] + summary['invalid_first_seen'])
    assert classified == summary['total']


# ---------------------------------------------------------------------------
# 19. Progress logger called once
# ---------------------------------------------------------------------------

def test_progress_logger_called_once_with_summary():
    """ProgressLogger-style logger -- the most common case in production."""
    class FakeProgress(object):
        def __init__(self):
            self.calls = []

        def log_without_increment(self, message):
            self.calls.append(message)

    relay = _make_relay()
    uptime = _make_uptime(periods={
        '5_years': {'first': '2025-03-08 00:00:00', 'interval': 864000, 'values': [999]},
    })
    data = _make_relay_data(relay)
    fake = FakeProgress()
    correct_first_seen(data, uptime, progress_logger=fake)
    assert len(fake.calls) == 1
    assert '1/1' in fake.calls[0]
    assert 'first-seen' in fake.calls[0].lower() or 'first_seen' in fake.calls[0].lower()


# ---------------------------------------------------------------------------
# 20. Logger shape agnostic
# ---------------------------------------------------------------------------

def test_logger_shape_agnostic():
    relay = _make_relay()
    uptime = _make_uptime(periods={
        '5_years': {'first': '2025-03-08 00:00:00', 'interval': 864000, 'values': [999]},
    })

    # (a) ProgressLogger-like
    class ProgressLike(object):
        def __init__(self):
            self.calls = []

        def log_without_increment(self, msg):
            self.calls.append(msg)

    p = ProgressLike()
    correct_first_seen(_make_relay_data(_make_relay()), uptime, progress_logger=p)
    assert len(p.calls) == 1

    # (b) logging.Logger-like
    captured = []
    logger = logging.getLogger('first_seen_correction_test')
    logger.setLevel(logging.DEBUG)
    # Install a handler that captures records.
    class CaptureHandler(logging.Handler):
        def emit(self, record):
            captured.append(record.getMessage())
    handler = CaptureHandler()
    logger.addHandler(handler)
    try:
        correct_first_seen(_make_relay_data(_make_relay()), uptime,
                           progress_logger=logger)
        assert len(captured) == 1
    finally:
        logger.removeHandler(handler)

    # (c) bare callable
    captured_callable = []
    correct_first_seen(_make_relay_data(_make_relay()), uptime,
                       progress_logger=lambda msg: captured_callable.append(msg))
    assert len(captured_callable) == 1

    # (d) None -- no crash
    correct_first_seen(_make_relay_data(_make_relay()), uptime,
                       progress_logger=None)

    # (e) noisy logger -- must not propagate
    def raising_logger(msg):
        raise RuntimeError('boom')

    correct_first_seen(_make_relay_data(_make_relay()), uptime,
                       progress_logger=raising_logger)


# ---------------------------------------------------------------------------
# 21. Correction metadata fields gated on actual change
# ---------------------------------------------------------------------------

def test_correction_metadata_fields_set_only_on_corrected_relays():
    # Already tested in test_first_seen_onionoo_raw_only_added_when_changed,
    # but assert the two metadata fields specifically here too.
    relay_corrected = _make_relay(fingerprint='AAAA' + 'A' * 36)
    relay_unchanged = _make_relay(first_seen='2024-01-01 00:00:00',
                                  fingerprint='BBBB' + 'B' * 36)

    uptime = {
        'relays': [
            {'fingerprint': 'AAAA' + 'A' * 36, 'uptime': {'5_years': {
                'first': '2025-03-08 00:00:00', 'interval': 864000, 'values': [999]}}},
            {'fingerprint': 'BBBB' + 'B' * 36, 'uptime': {'5_years': {
                'first': '2024-06-01 00:00:00', 'interval': 864000, 'values': [999]}}},
        ],
    }
    data = _make_relay_data(relay_corrected, relay_unchanged)
    correct_first_seen(data, uptime)

    assert relay_corrected.get('_first_seen_corrected') is True
    assert relay_corrected.get('_first_seen_correction_source') == 'onionoo_uptime'

    assert '_first_seen_corrected' not in relay_unchanged
    assert '_first_seen_correction_source' not in relay_unchanged


# ---------------------------------------------------------------------------
# Direct tests of _earliest_uptime_interval helper
# ---------------------------------------------------------------------------

def test_earliest_uptime_interval_returns_none_for_non_dict():
    assert _earliest_uptime_interval(None) is None
    assert _earliest_uptime_interval('garbage') is None
    assert _earliest_uptime_interval([]) is None
    assert _earliest_uptime_interval({'uptime': 'not-a-dict'}) is None


def test_earliest_uptime_interval_skips_negative_interval():
    """Defensive: a negative or zero interval must not be used."""
    uptime_relay = {
        'fingerprint': FP,
        'uptime': {
            '5_years': {
                'first': '2025-03-08 00:00:00',
                'interval': -1,
                'values': [999],
            },
        },
    }
    assert _earliest_uptime_interval(uptime_relay) is None


# ---------------------------------------------------------------------------
# Upper-bound comparison: avoid spurious "corrections" when /details and
# /uptime are already in agreement to within bucket precision.
# ---------------------------------------------------------------------------

def test_no_spurious_correction_when_first_seen_falls_inside_uptime_interval():
    """If /details' first_seen falls inside the uptime interval, the relay
    could have been first observed at that exact time -- /details and /uptime
    don't disagree, so no correction.
    """
    # Uptime: first=2025-01-03 (midpoint), interval=864000 (10d, half=5d).
    # Interval 0 covers [2024-12-29, 2025-01-08].
    # /details first_seen=2025-01-05 falls INSIDE this interval -- consistent.
    relay = _make_relay(first_seen='2025-01-05 00:00:00')
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2025-01-03 00:00:00',
            'interval': 864000,
            'values': [999, 999],
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    assert relay['first_seen'] == '2025-01-05 00:00:00'
    assert 'first_seen_onionoo_raw' not in relay
    assert data['_first_seen_correction_summary']['unchanged'] == 1


def test_relays_list_with_non_dict_entries_is_robust():
    """Defensive: a non-dict entry in relays must not crash anything; it's
    counted under non_dict_skipped (outside ``total``)."""
    data = {'relays': [_make_relay(), 'garbage', None, 42]}
    uptime = _make_uptime(periods={
        '5_years': {'first': '2025-03-08 00:00:00', 'interval': 864000,
                    'values': [999]},
    })
    correct_first_seen(data, uptime)
    # The real relay was corrected; the garbage entries were silently skipped.
    assert data['relays'][0]['_first_seen_corrected'] is True
    summary = data['_first_seen_correction_summary']
    assert summary['total'] == 1, 'total counts only dict relays'
    assert summary['corrected'] == 1
    assert summary['non_dict_skipped'] == 3, '3 garbage entries skipped'


def test_relays_field_is_dict_not_list_is_robust():
    """Defensive: relay_data['relays'] is a dict, not a list."""
    data = {'relays': {'oops': 'this should be a list'}}
    correct_first_seen(data, _make_uptime())
    # Short-circuited; summary has total=0.
    assert data['_first_seen_correction_summary']['total'] == 0


def test_relay_data_none_returns_none():
    """correct_first_seen(None, ...) must not crash."""
    result = correct_first_seen(None, _make_uptime())
    assert result is None


def test_uptime_data_is_garbage_string():
    """If uptime_data is not a dict at all, treat as missing."""
    relay = _make_relay()
    data = _make_relay_data(relay)
    correct_first_seen(data, 'not a dict')
    assert relay['first_seen'] == '2026-04-06 23:00:00'
    assert data['_first_seen_correction_summary']['missing_uptime'] == 1


def test_corrects_when_first_seen_just_past_upper_bound():
    """When /details first_seen is just past the upper bound of uptime's
    earliest non-null interval, correction must trigger and yield the
    interval midpoint.
    """
    # Uptime: first=2025-01-03 (midpoint), interval=864000s (10d, half=5d).
    # Interval 0 covers [2024-12-29, 2025-01-08].
    # /details first_seen=2025-01-09 is 1 day past upper bound -> correct.
    relay = _make_relay(first_seen='2025-01-09 00:00:00')
    uptime = _make_uptime(periods={
        '5_years': {
            'first': '2025-01-03 00:00:00',
            'interval': 864000,
            'values': [999],
        },
    })
    data = _make_relay_data(relay)
    correct_first_seen(data, uptime)
    # Corrected to midpoint = 2025-01-03 (== `first` for idx=0).
    assert relay['first_seen'] == '2025-01-03 00:00:00'
    assert relay['first_seen_onionoo_raw'] == '2025-01-09 00:00:00'
