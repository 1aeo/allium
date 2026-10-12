"""
Tests for the downtime filter, Relays._filter_and_fix_relays.

Onionoo keeps offline relays inconsistently, and can keep marking a relay as
running months after its last consensus. The filter drops relays not seen
within filter_downtime_days of the details document's publish time, whether
or not Onionoo still marks them as running.
"""

import unittest
from datetime import datetime, timedelta, timezone

from allium.lib.progress_logger import ProgressLogger
from allium.lib.relays import Relays

PUBLISHED = '2026-10-11 20:00:00'


def relay(fingerprint, running, last_seen=None):
    """A minimal details-document relay"""
    entry = {'fingerprint': fingerprint, 'running': running}
    if last_seen:
        entry['last_seen'] = last_seen
    return entry


def kept(relays, days=14, published=PUBLISHED):
    """Fingerprints the downtime filter keeps, from a details document with the given publish time"""
    obj = Relays.__new__(Relays)
    obj.json = {'relays': relays}
    if published:
        obj.json['relays_published'] = published
    obj.filter_downtime_days = days
    obj.progress = False
    obj.progress_logger = ProgressLogger(progress_enabled=False)
    obj._filter_and_fix_relays()
    return [r['fingerprint'] for r in obj.json['relays']]


def ago(**delta):
    """An Onionoo timestamp the given time before now"""
    return (datetime.now(timezone.utc) - timedelta(**delta)).strftime('%Y-%m-%d %H:%M:%S')


class TestDowntimeFilter(unittest.TestCase):
    """Which relays the downtime filter keeps"""

    def test_running_relay_in_latest_consensus_is_kept(self):
        """last_seen equals relays_published for every relay in the latest consensus"""
        self.assertEqual(kept([relay('A', True, PUBLISHED)]), ['A'])

    def test_running_relay_not_seen_since_april_is_dropped(self):
        """Onionoo still marks it running, but its last consensus was 6 Apr"""
        self.assertEqual(kept([relay('A', True, '2026-04-06 22:00:00')]), [])

    def test_running_relay_without_last_seen_is_kept(self):
        """Without a last_seen there is nothing to measure"""
        self.assertEqual(kept([relay('A', True)]), ['A'])

    def test_offline_relays_within_and_beyond_the_cutoff(self):
        """Offline 6.5 days is kept, 15 days is dropped, no last_seen is dropped"""
        relays = [relay('RECENT', False, '2026-10-05 07:00:00'), relay('OLD', False, '2026-09-26 20:00:00'),
                  relay('NONE', False)]
        self.assertEqual(kept(relays), ['RECENT'])

    def test_cutoff_is_measured_from_relays_published(self):
        """A relay seen 10 days before the snapshot is within 14 days, however late allium runs"""
        self.assertEqual(kept([relay('A', False, '2026-10-01 20:00:00'), relay('B', True, '2026-10-01 20:00:00')]),
                         ['A', 'B'])
        self.assertEqual(kept([relay('A', False, '2026-10-01 20:00:00')], days=7), [])

    def test_without_relays_published_running_relays_are_kept_and_offline_ones_measured_from_now(self):
        """No publish time to compare with: running relays stay, as before"""
        relays = [relay('RUNNING', True, '2024-01-01 12:00:00'), relay('RECENT', False, ago(days=1)),
                  relay('OLD', False, ago(days=20))]
        self.assertEqual(kept(relays, published=None), ['RUNNING', 'RECENT'])

    def test_zero_days_keeps_everything_and_fixes_bandwidth(self):
        """--filter-downtime 0 disables filtering; missing observed_bandwidth still becomes 0"""
        relays = [relay('A', True, '2026-04-06 22:00:00'), relay('B', False, '2020-01-01 00:00:00')]
        self.assertEqual(kept(relays, days=0), ['A', 'B'])
        self.assertEqual([r['observed_bandwidth'] for r in relays], [0, 0])


if __name__ == '__main__':
    unittest.main()
