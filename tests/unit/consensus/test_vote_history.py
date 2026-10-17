"""Fixture-vote tests for the per-relay measurement history.

Votes are built in memory. These tests do not download CollecTor.
"""

import os
from datetime import datetime, timedelta, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from allium.lib.consensus.collector_fetcher import CollectorFetcher
from allium.lib.consensus.vote_history import (
    CHART_MAX_POINTS,
    attach_relay_vote_views,
    classify_authority_votes,
    consensus_weight_median,
    document_time,
    empty_store,
    format_relay_history,
    load_history,
    record_votes,
    save_history,
    summarize_operator_votes,
    update_history_from_collector,
)

FP = 'A' * 40
FP_B = 'B' * 40
HOUR_1 = '2026-10-17 11:00:00'
HOUR_2 = '2026-10-17 12:00:00'
OLD = '2026-10-02 00:00:00'
KEPT = '2026-10-03 00:00:00'
NEWEST = '2026-10-17 00:00:00'

FLAGS = ['Fast', 'Guard', 'Running', 'Stable', 'Valid']


def _relay(measured, bandwidth, flags=None):
    return {
        'measured': measured,
        'bandwidth': bandwidth,
        'flags': list(FLAGS if flags is None else flags),
    }


def _vote(when, relays, published=None):
    return {
        'valid_after': when,
        'published': published or when,
        'vote_time': when,
        'relays': relays,
    }


def _measured_votes(when, values):
    """Three or more Measured= values, plus one relay-reported-only authority."""
    relays_by_auth = {}
    votes = {}
    for name, measured in values.items():
        relays_by_auth[name] = {
            FP: _relay(measured, 40 if measured is None else 10),
            FP_B: _relay(5, 5),  # keeps the authority in the measuring set
        }
        votes[name] = _vote(when, relays_by_auth[name])
    return votes


class TestConsensusWeightMedian:
    """The stored median matches CollectorFetcher._format_bandwidth."""

    def _fetcher(self, votes_for_a, extra_measured=True):
        fetcher = CollectorFetcher()
        votes_a = {}
        for name, (measured, bandwidth) in votes_for_a.items():
            votes_a[name] = {'measured': measured, 'bandwidth': bandwidth, 'flags': FLAGS}
        index = {FP: {'votes': votes_a}}
        if extra_measured:
            index[FP_B] = {'votes': {
                name: {'measured': 5, 'bandwidth': 5, 'flags': FLAGS}
                for name in votes_for_a
            }}
        fetcher.relay_index = index
        fetcher.bw_authorities = set()
        return fetcher

    def test_low_median_of_measured_matches_fetcher(self):
        votes = {
            'bastet': (100, 10),
            'longclaw': (400, 10),
            'moria1': (200, 10),
            'tor26': (300, 10),
            'dizum': (None, 999),
        }
        fetcher = self._fetcher(votes)
        formatted = fetcher._format_bandwidth(fetcher.relay_index[FP])
        median_kb, unmeasured, cap = consensus_weight_median(
            [100, 400, 200, 300, None],
            [10, 10, 10, 10, 999],
            measuring_count=5,
        )
        # Even count of Measured=: 100, 200, 300, 400 -> lower median 200.
        assert formatted['unmeasured'] is False
        assert formatted['median'] == 200 * 1000
        assert (median_kb, unmeasured, cap) == (200, False, False)

    def test_unmeasured_bandwidth_median_is_capped(self):
        votes = {
            'bastet': (None, 100),
            'longclaw': (None, 80),
            'moria1': (None, 40),
        }
        fetcher = self._fetcher(votes, extra_measured=True)
        formatted = fetcher._format_bandwidth(fetcher.relay_index[FP])
        median_kb, unmeasured, cap = consensus_weight_median(
            [None, None, None],
            [100, 80, 40],
            measuring_count=3,
        )
        # Low median of 40, 80, 100 is 80, then maxunmeasuredbw caps it at 20.
        assert formatted['unmeasured'] is True
        assert formatted['median'] == 20 * 1000
        assert (median_kb, unmeasured, cap) == (20, True, True)

    def test_unmeasured_without_three_measuring_authorities_is_not_capped(self):
        median_kb, unmeasured, cap = consensus_weight_median(
            [None, None],
            [100, 80],
            measuring_count=2,
        )
        assert (median_kb, unmeasured, cap) == (80, True, False)


class TestRecordVotes:
    def test_document_time_is_valid_after_and_published_is_the_fallback(self):
        assert document_time({'vote_time': HOUR_1, 'valid_after': HOUR_2}) == HOUR_1
        assert document_time({'valid_after': HOUR_2, 'published': HOUR_1}) == HOUR_2
        assert document_time({'published': '2026-10-17T12:00:00Z'}) == HOUR_2
        assert document_time({'relays': {}}) is None

    def test_periods_stay_separate_and_rerecording_is_a_noop(self):
        first = _measured_votes(HOUR_1, {
            'bastet': 100, 'longclaw': 200, 'moria1': 300, 'tor26': 400,
        })
        store, changed = record_votes(empty_store(), first)
        assert changed is True
        second = _measured_votes(HOUR_2, {
            'bastet': 10, 'longclaw': None, 'moria1': None,
        })
        # Hour 2's longclaw/moria1 votes have no Measured= for FP but do for FP_B,
        # and bastet measured 10. Only one Measured= for FP, so its median is Bandwidth=.
        store, changed = record_votes(store, second)
        assert changed is True
        entry = store['relays'][FP]
        assert entry['t'] == [HOUR_1, HOUR_2]
        assert entry['median'][0] == 200
        assert entry['unmeasured'][0] == 0
        assert entry['median'][1] != 200
        assert entry['unmeasured'][1] == 1
        again, changed = record_votes(store, first)
        again, changed = record_votes(again, second)
        assert changed is False
        assert again['relays'][FP]['t'] == [HOUR_1, HOUR_2]
        assert again['relays'][FP]['median'] == entry['median']

    def test_late_authority_merges_into_the_same_document(self):
        early = {
            'moria1': _vote(HOUR_1, {FP: _relay(100, 50)}),
        }
        store, _changed = record_votes(empty_store(), early)
        assert store['relays'][FP]['median'] == [50]
        assert store['relays'][FP]['unmeasured'] == [1]
        late = {
            'bastet': _vote(HOUR_1, {FP: _relay(200, 10), FP_B: _relay(5, 5)}),
            'longclaw': _vote(HOUR_1, {FP: _relay(300, 10), FP_B: _relay(5, 5)}),
            'tor26': _vote(HOUR_1, {FP: _relay(400, 10), FP_B: _relay(5, 5)}),
        }
        store, changed = record_votes(store, late)
        assert changed is True
        assert store['relays'][FP]['t'] == [HOUR_1]
        # Measured= 100, 200, 300, 400 -> lower median 200. moria1's value is kept.
        assert store['relays'][FP]['median'] == [200]
        assert store['relays'][FP]['unmeasured'] == [0]

    def test_prune_keeps_fourteen_days_before_the_newest_document(self):
        store = empty_store()
        for when, measured in ((OLD, 10), (KEPT, 20), (NEWEST, 30)):
            store, _changed = record_votes(store, {
                'moria1': _vote(when, {FP: _relay(None, measured)}),
            })
        assert store['relays'][FP]['t'] == [KEPT, NEWEST]

    def test_save_and_load_round_trip(self, tmp_path):
        votes = _measured_votes(HOUR_1, {'bastet': 100, 'longclaw': 200, 'moria1': 300})
        store, _changed = record_votes(empty_store(), votes)
        path = os.path.join(str(tmp_path), 'vote_history.json.gz')
        save_history(store, path)
        loaded = load_history(path)
        assert loaded['relays'][FP]['median'] == store['relays'][FP]['median']
        assert loaded['relays'][FP]['t'] == [HOUR_1]
        assert update_history_from_collector({'votes': votes}, path) == len(loaded['relays'])
        # Same documents: the file is left as written.
        before = open(path, 'rb').read()
        assert update_history_from_collector({'votes': votes}, path) == len(loaded['relays'])
        assert open(path, 'rb').read() == before

    def test_lower_case_fingerprint_is_stored_once(self):
        vote = _vote(HOUR_1, {FP.lower(): _relay(100, 10)})
        store, _changed = record_votes(empty_store(), {'moria1': vote})
        assert list(store['relays']) == [FP]

    def test_missing_document_time_is_skipped(self):
        vote = {'relays': {FP: _relay(100, 10)}}
        store, changed = record_votes(empty_store(), {'moria1': vote})
        assert changed is False
        assert store['relays'] == {}


class TestFormatAndAgreement:
    def _history(self):
        flags_off = ['Fast', 'Running', 'Stable', 'Valid']
        first = {
            'bastet': _vote(HOUR_1, {FP: _relay(100, 10)}),
            'longclaw': _vote(HOUR_1, {FP: _relay(300, 10)}),
            'moria1': _vote(HOUR_1, {FP: _relay(500, 10)}),
        }
        second = {
            'bastet': _vote(HOUR_2, {FP: _relay(110, 10, flags_off)}),
            'longclaw': _vote(HOUR_2, {FP: _relay(310, 10)}),
            'moria1': _vote(HOUR_2, {FP: _relay(510, 10)}),
        }
        # A third authority keeps both hours on the measured path.
        store, _changed = record_votes(empty_store(), first)
        store, _changed = record_votes(store, second)
        return store

    def test_view_names_the_document_time_and_the_median(self):
        view = format_relay_history(self._history(), FP, use_bits=False)
        assert view['point_count'] == 2
        assert view['rows'][0]['valid_after'] == HOUR_2
        assert view['rows'][1]['valid_after'] == HOUR_1
        assert view['rows'][0]['unmeasured'] is False
        assert 'KB/s' in view['rows'][0]['median_title'] or 'median' in view['rows'][0]['median_title']
        names = [column['name'] for column in view['columns']]
        assert names == sorted(names, key=str.lower)
        bastet = names.index('bastet')
        assert view['rows'][0]['cells'][bastet]['mark'] == 'M'
        assert HOUR_2 in view['rows'][0]['cells'][bastet]['title']
        assert view['rows'][0]['guard_delta'] == -1
        assert view['rows'][0]['guard'] == '2/3'
        assert view['svg']
        assert HOUR_1 in view['svg']
        assert HOUR_2 in view['svg']
        assert 'Onionoo traffic' in view['svg']

    def test_single_document_has_no_chart(self):
        store, _changed = record_votes(empty_store(), {
            'moria1': _vote(HOUR_1, {FP: _relay(100, 10)}),
        })
        view = format_relay_history(store, FP, use_bits=True)
        assert view['svg'] is None
        assert view['rows'][0]['valid_after'] == HOUR_1
        assert 'Mbit/s' in view['rows'][0]['cells'][0]['display'] or 'Kbit/s' in view['rows'][0]['cells'][0]['display']

    def test_chart_axis_follows_document_time(self):
        early = '2026-10-07 00:00:00'
        mid = '2026-10-07 01:00:00'
        late = '2026-10-17 00:00:00'
        store = empty_store()
        for when in (early, mid, late):
            store, _changed = record_votes(store, {
                'moria1': _vote(when, {FP: _relay(100, 10)}),
                'bastet': _vote(when, {FP: _relay(300, 10)}),
                'longclaw': _vote(when, {FP: _relay(500, 10)}),
            })
        view = format_relay_history(store, FP, use_bits=False)
        points = view['svg'].split('points="', 1)[1].split('"', 1)[0]
        xs = [int(pair.split(',')[0]) for pair in points.split()]
        # One hour after the first document sits near the left edge, not halfway
        # across a ten-day span.
        assert xs[1] - xs[0] < (xs[2] - xs[0]) / 5

    def test_reported_value_is_gray_when_measurements_decide_the_median(self):
        store, _changed = record_votes(empty_store(), _measured_votes(HOUR_1, {
            'bastet': 100, 'longclaw': 200, 'moria1': 300, 'dizum': None,
        }))
        view = format_relay_history(store, FP, use_bits=False)
        cells = {view['columns'][i]['name']: view['rows'][0]['cells'][i]
                 for i in range(len(view['columns']))}
        assert cells['dizum']['mark'] == 'R'
        assert cells['dizum']['counts'] is False
        assert cells['bastet']['counts'] is True

    def test_classify_and_operator_summary(self):
        agreed = classify_authority_votes({
            'moria1': {'flags': FLAGS, 'measured': 100},
            'bastet': {'flags': list(FLAGS), 'measured': 120},
        })
        assert agreed['agreed'] is True
        assert agreed['measurement_split'] is False
        assert agreed['unmeasured'] is True  # only two Measured= values

        split = classify_authority_votes({
            'moria1': {'flags': FLAGS, 'measured': 100},
            'bastet': {'flags': ['Fast', 'Running', 'Stable', 'Valid'], 'measured': None},
            'longclaw': {'flags': FLAGS, 'measured': 80},
        })
        assert split['agreed'] is False
        assert 'Guard' in split['split_flags']
        assert split['measurement_split'] is True
        # A non-scanner authority with no Measured= is not a measurement split
        # once the caller names the authorities that run bandwidth scanners.
        scanners = classify_authority_votes({
            'moria1': {'flags': FLAGS, 'measured': 100},
            'bastet': {'flags': FLAGS, 'measured': 120},
            'longclaw': {'flags': FLAGS, 'measured': None},
        }, measuring_authorities={'moria1', 'bastet'})
        assert scanners['measurement_split'] is False
        missed = classify_authority_votes({
            'moria1': {'flags': FLAGS, 'measured': 100},
            'bastet': {'flags': FLAGS, 'measured': None},
        }, measuring_authorities={'moria1', 'bastet'})
        assert missed['measurement_split'] is True
        assert classify_authority_votes({}) is None

        summary = summarize_operator_votes([
            {'nickname': 'split-guard', 'fingerprint': FP, 'vote_agreement': split},
            {'nickname': 'ok', 'fingerprint': FP_B, 'vote_agreement': agreed},
            {'nickname': 'no-votes', 'fingerprint': 'C' * 40},
        ])
        assert summary['compared'] == 2
        assert summary['agreed'] == 1
        assert summary['split'] == 1
        assert summary['examples'][0]['nickname'] == 'split-guard'
        assert 'Guard' in summary['examples'][0]['flags_display']

    def test_attach_views_counts_the_network(self):
        store, _changed = record_votes(empty_store(), {
            'moria1': _vote(HOUR_1, {FP: _relay(100, 10), FP_B: _relay(None, 40, ['Running', 'Valid'])}),
            'bastet': _vote(HOUR_1, {FP: _relay(200, 10), FP_B: _relay(None, 50, ['Running', 'Valid', 'Guard'])}),
        })
        relays = [
            {'fingerprint': FP, 'nickname': 'measured'},
            {'fingerprint': FP_B, 'nickname': 'split'},
        ]
        index = {
            FP: {'votes': {
                'moria1': {'flags': FLAGS, 'measured': 100},
                'bastet': {'flags': FLAGS, 'measured': 200},
            }},
            FP_B: {'votes': {
                'moria1': {'flags': ['Running', 'Valid'], 'measured': None},
                'bastet': {'flags': ['Running', 'Valid', 'Guard'], 'measured': None},
            }},
        }
        summary = attach_relay_vote_views(relays, store, index, use_bits=False)
        assert summary['compared'] == 2
        assert summary['split'] == 1
        assert relays[0]['vote_history']['rows'][0]['valid_after'] == HOUR_1
        assert relays[1]['vote_agreement']['split_flags'] == ['Guard']
        assert any(item['flag'] == 'Guard' and item['count'] == 1 for item in summary['split_flags'])

    def test_chart_window_is_bounded(self):
        store = empty_store()
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        for offset in range(CHART_MAX_POINTS + 5):
            when = (start + timedelta(hours=offset)).strftime('%Y-%m-%d %H:%M:%S')
            store, _changed = record_votes(store, {
                'moria1': _vote(when, {FP: _relay(100 + offset, 10)}),
                'bastet': _vote(when, {FP: _relay(200 + offset, 10)}),
                'longclaw': _vote(when, {FP: _relay(300 + offset, 10)}),
            })
        view = format_relay_history(store, FP, use_bits=False)
        assert view['point_count'] == CHART_MAX_POINTS + 5
        assert view['chart_truncated'] is True
        assert view['chart_count'] == CHART_MAX_POINTS
        assert len(view['rows']) == 24


def test_vote_history_template_shows_document_time(tmp_path):
    store, _changed = record_votes(empty_store(), _measured_votes(HOUR_1, {
        'bastet': 100, 'longclaw': 200, 'moria1': 300,
    }))
    store, _changed = record_votes(store, _measured_votes(HOUR_2, {
        'bastet': 150, 'longclaw': 250, 'moria1': 350,
    }))
    view = format_relay_history(store, FP, use_bits=False)
    env = Environment(
        loader=FileSystemLoader('allium/templates'),
        autoescape=select_autoescape(['html']),
    )
    html = env.get_template('vote-history.html').render(relay={'vote_history': view})
    assert 'id="vote-history"' in html
    assert HOUR_1 in html
    assert HOUR_2 in html
    assert 'Measured=' in html
    assert 'Onionoo write/read charts elsewhere on this page are traffic.' in html
    assert '<svg' in html
    assert 'computing-consensus.html' in html
    # The SVG is emitted as markup, not escaped text.
    assert '&lt;svg' not in html
