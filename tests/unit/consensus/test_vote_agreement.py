"""Current-hour vote agreement and the consensus-weight median. No stored history."""

from allium.lib.consensus.collector_fetcher import (
    CollectorFetcher,
    consensus_weight_median,
    document_time,
)
from allium.lib.consensus.vote_agreement import (
    attach_vote_agreement,
    classify_authority_votes,
    summarize_operator_votes,
)

FP = 'A' * 40
FP_B = 'B' * 40
HOUR_1 = '2026-10-17 11:00:00'
HOUR_2 = '2026-10-17 12:00:00'
FLAGS = ['Fast', 'Guard', 'Running', 'Stable', 'Valid']


class TestConsensusWeightMedian:
    def _fetcher(self, votes_for_a, extra_measured=True):
        fetcher = CollectorFetcher()
        votes_a = {
            name: {'measured': measured, 'bandwidth': bandwidth, 'flags': FLAGS}
            for name, (measured, bandwidth) in votes_for_a.items()
        }
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
            [100, 400, 200, 300, None], [10, 10, 10, 10, 999], measuring_count=5)
        assert formatted['unmeasured'] is False
        assert formatted['median'] == 200 * 1000
        assert (median_kb, unmeasured, cap) == (200, False, False)

    def test_unmeasured_bandwidth_median_is_capped(self):
        votes = {
            'bastet': (None, 100),
            'longclaw': (None, 80),
            'moria1': (None, 40),
        }
        fetcher = self._fetcher(votes)
        formatted = fetcher._format_bandwidth(fetcher.relay_index[FP])
        assert formatted['median'] == 20 * 1000
        assert consensus_weight_median([None, None, None], [100, 80, 40], 3) == (20, True, True)

    def test_live_median_uses_only_the_newest_vote_hour(self):
        fetcher = CollectorFetcher()
        fetcher.votes = {
            'bastet': {'valid_after': HOUR_2, 'vote_time': HOUR_2},
            'longclaw': {'valid_after': HOUR_2, 'vote_time': HOUR_2},
            'moria1': {'valid_after': HOUR_1, 'vote_time': HOUR_1},
        }
        fetcher.relay_index = {
            FP: {'votes': {
                'bastet': {'measured': None, 'bandwidth': 100},
                'longclaw': {'measured': None, 'bandwidth': 80},
                'moria1': {'measured': None, 'bandwidth': 40},
            }},
            FP_B: {'votes': {
                name: {'measured': 5, 'bandwidth': 5}
                for name in ('bastet', 'longclaw', 'moria1')
            }},
        }
        fetcher.bw_authorities = set()
        assert fetcher._format_bandwidth(fetcher.relay_index[FP])['median'] == 80 * 1000
        bare = CollectorFetcher()
        bare.relay_index = fetcher.relay_index
        bare.bw_authorities = set()
        assert bare._format_bandwidth(bare.relay_index[FP])['median'] == 20 * 1000

    def test_document_time_prefers_vote_time(self):
        assert document_time({'vote_time': HOUR_1, 'valid_after': HOUR_2}) == HOUR_1
        assert document_time({'published': '2026-10-17T12:00:00Z'}) == HOUR_2


class TestAgreement:
    def test_classify_and_operator_summary(self):
        agreed = classify_authority_votes({
            'moria1': {'flags': FLAGS, 'measured': 100},
            'bastet': {'flags': list(FLAGS), 'measured': 120},
        })
        assert agreed['agreed'] is True
        assert agreed['unmeasured'] is True
        split = classify_authority_votes({
            'moria1': {'flags': FLAGS, 'measured': 100},
            'bastet': {'flags': ['Fast', 'Running', 'Stable', 'Valid'], 'measured': None},
            'longclaw': {'flags': FLAGS, 'measured': 80},
        })
        assert 'Guard' in split['split_flags']
        assert split['measurement_split'] is True
        folded = classify_authority_votes({
            'Moria1': {'flags': FLAGS, 'measured': 100},
            'bastet': {'flags': FLAGS, 'measured': None},
        }, measuring_authorities={'moria1', 'bastet'})
        assert folded['measurement_split'] is True
        quiet = classify_authority_votes({
            'moria1': {'flags': FLAGS, 'measured': False},
            'bastet': {'flags': FLAGS, 'measured': None},
        }, measuring_authorities=set())
        assert quiet['measurement_split'] is False
        duplicated = classify_authority_votes({
            'moria1': {'flags': ['Guard', 'Guard'] + FLAGS[1:], 'measured': 10},
            'bastet': {'flags': ['Fast', 'Running', 'Stable', 'Valid'], 'measured': 10},
        })
        assert 'Guard' in duplicated['split_flags']
        summary = summarize_operator_votes([
            {'nickname': 'split-guard', 'fingerprint': FP, 'vote_agreement': split},
            {'nickname': 'ok', 'fingerprint': FP_B, 'vote_agreement': agreed},
            {'nickname': 'no-votes', 'fingerprint': 'C' * 40},
        ])
        assert summary['compared'] == 2
        assert summary['examples'][0]['nickname'] == 'split-guard'
        assert summary['flag_rows'][0]['flag'] == 'Running'
        guard = [row for row in summary['flag_rows'] if row['flag'] == 'Guard'][0]
        assert guard == {'flag': 'Guard', 'agreed': 1, 'split': 1}

    def test_fast_pattern_names_who_withheld_then_who_assigned(self):
        relays = []
        for index in range(64):
            no = ['faravahar'] if index < 61 else ['faravahar', 'moria1']
            yes = ['bastet', 'dannenberg', 'gabelmoo', 'tor26']
            if index < 61:
                yes.append('moria1')
            relays.append({
                'nickname': 'r%02d' % index,
                'fingerprint': 'A' * 39 + '%X' % (index % 16),
                'vote_agreement': {
                    'agreed': False,
                    'split_flags': ['Fast'],
                    'measurement_split': False,
                    'unmeasured': False,
                    'flag_sides': {'Fast': {'no': sorted(no), 'yes': sorted(yes)}},
                    'measured_by': ['bastet', 'gabelmoo'],
                    'voters': ['bastet'],
                    'assigned_flags': [],
                    'absent_flags': [],
                },
            })
        summary = summarize_operator_votes(relays, measurement_authorities={
            'publishing': ['bastet', 'gabelmoo'],
            'silent': ['faravahar', 'longclaw'],
            'scanners': ['bastet', 'faravahar', 'gabelmoo', 'longclaw'],
        })
        lines = summary['flag_patterns'][0]['lines']
        assert lines[0]['kind'] == 'did_not' and lines[0]['scope'] == 'all'
        assert lines[0]['names'] == ['faravahar'] and lines[0]['count'] == 64
        assert lines[1]['scope'] == 'of_those' and lines[1]['names'] == ['moria1'] and lines[1]['count'] == 3
        assert lines[2]['kind'] == 'assigned' and lines[2]['scope'] == 'all'
        assert lines[2]['names'] == ['bastet', 'dannenberg', 'gabelmoo', 'tor26']
        assert summary['example_total'] == 64
        assert len(summary['examples']) == 5
        assert summary['examples'][0]['nickname'] == 'r00'
        assert summary['bandwidth']['full_count'] == 64
        assert summary['bandwidth']['silent'] == ['faravahar', 'longclaw']

    def test_guard_groups_list_withheld_flags_before_assigned_flags(self):
        def relay(name, no, yes):
            return {
                'nickname': name, 'fingerprint': 'B' * 40,
                'vote_agreement': {
                    'agreed': False, 'split_flags': ['Guard'], 'measurement_split': False,
                    'unmeasured': False, 'measured_by': ['bastet'],
                    'flag_sides': {'Guard': {'no': no, 'yes': yes}},
                    'voters': [], 'assigned_flags': [], 'absent_flags': [],
                },
            }
        relays = (
            [relay('a%d' % i, ['bastet'], ['moria1', 'dannenberg', 'tor26']) for i in range(4)]
            + [relay('b%d' % i, ['bastet', 'dannenberg'], ['moria1', 'tor26']) for i in range(2)]
            + [relay('c%d' % i, ['bastet', 'dannenberg', 'tor26'], ['moria1']) for i in range(3)]
            + [relay('d0', ['dannenberg'], ['bastet', 'moria1', 'tor26'])]
        )
        lines = summarize_operator_votes(relays)['flag_patterns'][0]['lines']
        assert [(line['kind'], line['count'], line['names'], line['only']) for line in lines] == [
            ('did_not', 4, ['bastet'], True),
            ('did_not', 2, ['bastet', 'dannenberg'], False),
            ('assigned', 3, ['moria1'], True),
        ]

    def test_lowercase_index_key_still_counts(self):
        relays = [{'fingerprint': FP, 'nickname': 'x'}]
        index = {FP.lower(): {'votes': {'Moria1': {'flags': FLAGS, 'measured': 1}}}}
        summary = attach_vote_agreement(relays, index)
        assert summary['compared'] == 1
        assert relays[0]['vote_agreement']['agreed'] is True
