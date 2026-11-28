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

    def test_missing_count_includes_zero_measured_relays(self):
        """Relays with zero Measured= values count toward bandwidth missing_count."""
        relays = [
            {'fingerprint': FP, 'nickname': 'all-measured'},
            {'fingerprint': FP_B, 'nickname': 'partial-measured'},
            {'fingerprint': 'C' * 40, 'nickname': 'zero-measured'},
        ]
        index = {
            FP: {'votes': {
                'bastet': {'flags': FLAGS, 'measured': 100},
                'moria1': {'flags': FLAGS, 'measured': 120},
            }},
            FP_B: {'votes': {
                'bastet': {'flags': FLAGS, 'measured': 80},
                'moria1': {'flags': FLAGS, 'measured': None},
            }},
            'C' * 40: {'votes': {
                'bastet': {'flags': FLAGS, 'measured': None},
                'moria1': {'flags': FLAGS, 'measured': None},
            }},
        }
        summary = attach_vote_agreement(
            relays, index, bw_authorities={'bastet', 'moria1'},
            scanner_authorities={'bastet', 'moria1'},
        )
        assert summary['compared'] == 3
        assert summary['measurement_split'] == 1
        assert summary['bandwidth']['full_count'] == 1
        assert summary['bandwidth']['missing_count'] == 2
        assert summary['bandwidth']['misses'] == [
            {'name': 'moria1', 'count': 2},
            {'name': 'bastet', 'count': 1},
        ]

    def test_stale_vote_hour_excluded_to_match_consensus_weight(self):
        """Stale-hour Measured= votes are ignored so unmeasured agrees with CollectorFetcher."""
        index = {
            FP: {'votes': {
                'bastet': {'flags': FLAGS, 'measured': 100, 'bandwidth': 100},
                'longclaw': {'flags': FLAGS, 'measured': 120, 'bandwidth': 80},
                'moria1': {'flags': FLAGS, 'measured': 90, 'bandwidth': 60},
            }},
            FP_B: {'votes': {
                name: {'flags': FLAGS, 'measured': 5, 'bandwidth': 5}
                for name in ('bastet', 'longclaw', 'moria1')
            }},
        }
        votes_docs = {
            'bastet': {'valid_after': HOUR_2, 'vote_time': HOUR_2},
            'longclaw': {'valid_after': HOUR_2, 'vote_time': HOUR_2},
            'moria1': {'valid_after': HOUR_1, 'vote_time': HOUR_1},
        }
        fetcher = CollectorFetcher()
        fetcher.votes = votes_docs
        fetcher.relay_index = index
        fetcher.bw_authorities = {'bastet', 'longclaw', 'moria1'}
        bw_info = fetcher._format_bandwidth(index[FP])
        assert bw_info['measurement_count'] == 2
        assert bw_info['unmeasured'] is True

        relays_with_votes = [{'fingerprint': FP, 'nickname': 'lagged'}]
        summary = attach_vote_agreement(
            relays_with_votes, index,
            bw_authorities={'bastet', 'longclaw', 'moria1'},
            scanner_authorities={'bastet', 'longclaw', 'moria1'},
            votes=votes_docs,
        )
        assert relays_with_votes[0]['vote_agreement']['measured_count'] == 2
        assert relays_with_votes[0]['vote_agreement']['unmeasured'] is True
        assert summary['unmeasured'] == 1
        assert summary['bandwidth']['publishing'] == ['bastet', 'longclaw']
        assert summary['bandwidth']['missing_count'] == 0

        relays_no_votes = [{'fingerprint': FP, 'nickname': 'no-doc-hours'}]
        summary_all = attach_vote_agreement(
            relays_no_votes, index,
            bw_authorities={'bastet', 'longclaw', 'moria1'},
        )
        assert relays_no_votes[0]['vote_agreement']['measured_count'] == 3
        assert relays_no_votes[0]['vote_agreement']['unmeasured'] is False
        assert summary_all['unmeasured'] == 0

    def test_lagged_authority_excluded_from_table_reachability_and_eligibility(self):
        """Per-Authority Details, bandwidth, reachability, and agreement all filter lagged votes."""
        lagged_flags = ['Fast', 'Running', 'Stable', 'Valid']
        index = {
            FP: {'votes': {
                'bastet': {'flags': FLAGS, 'measured': 100, 'bandwidth': 100},
                'longclaw': {'flags': FLAGS, 'measured': 120, 'bandwidth': 80},
                'moria1': {'flags': lagged_flags, 'measured': 90, 'bandwidth': 60},
            }},
        }
        votes_docs = {
            'bastet': {'valid_after': HOUR_2, 'vote_time': HOUR_2},
            'longclaw': {'valid_after': HOUR_2, 'vote_time': HOUR_2},
            'moria1': {'valid_after': HOUR_1, 'vote_time': HOUR_1},
        }
        fetcher = CollectorFetcher()
        fetcher.votes = votes_docs
        fetcher.relay_index = index
        fetcher.bw_authorities = {'bastet', 'longclaw', 'moria1'}
        fetcher.flag_thresholds = {'bastet': {}, 'longclaw': {}, 'moria1': {}}

        assert fetcher.measuring_authorities == {'bastet', 'longclaw'}
        evaluation = fetcher.get_relay_consensus_evaluation(FP, authority_count=3)
        assert evaluation['vote_count'] == 2

        by_auth = {row['authority']: row for row in evaluation['authority_votes']}
        assert by_auth['bastet']['voted'] is True and by_auth['bastet']['measured'] == 100
        assert by_auth['longclaw']['voted'] is True and by_auth['longclaw']['measured'] == 120
        assert by_auth['moria1']['voted'] is False
        assert by_auth['moria1']['measured'] is None
        assert by_auth['moria1']['flags'] == []

        bw_info = evaluation['bandwidth']
        assert bw_info['measurement_count'] == 2
        assert bw_info['unmeasured'] is True
        assert bw_info['bw_auth_measured_count'] == 2
        assert bw_info['bw_auth_total'] == 2
        assert bw_info['bw_auth_not_measured_names'] == []

        reach = evaluation['reachability']
        assert reach['ipv4_reachable_count'] == 2
        assert 'moria1' not in reach['ipv4_reachable_authorities']

        guard_details = [d['authority'] for d in evaluation['flag_eligibility']['guard']['details']]
        assert sorted(guard_details) == ['bastet', 'longclaw']

        relays = [{'fingerprint': FP, 'nickname': 'agreed-current-hour'}]
        attach_vote_agreement(
            relays, index,
            bw_authorities=fetcher.measuring_authorities,
            scanner_authorities=fetcher.bw_authorities,
            votes=votes_docs,
        )
        assert relays[0]['vote_agreement']['agreed'] is True
        assert relays[0]['vote_agreement']['measured_count'] == 2
        assert relays[0]['vote_agreement']['unmeasured'] is True


class TestVoteAgreementMacroRendering:
    """Rendered bandwidth-measurement sentences distinguish publishing and silent authorities."""

    @staticmethod
    def _render_block(vote_sum):
        """Render vote_agreement_block with a minimal page_ctx."""
        import re
        from types import SimpleNamespace
        from allium.lib import page_writer

        tmpl = page_writer.ENV.from_string(
            "{% from 'macros.html' import vote_agreement_block %}{{ vote_agreement_block(vote_sum, page_ctx) }}"
        )
        html = tmpl.render(vote_sum=vote_sum, page_ctx=SimpleNamespace(path_prefix='../'))
        return ' '.join(re.sub(r'<[^>]+>', ' ', html).split())

    def test_full_coverage_names_publishing_and_silent_authorities_separately(self):
        """When all relays have Measured=, silent authorities still say no Measured= published."""
        vote_sum = {
            'agreed': 4, 'compared': 4, 'all_agreed': True, 'voters': ['bastet', 'gabelmoo'],
            'assigned_flags': FLAGS, 'absent_flags': [], 'split': 0, 'split_flags': [],
            'flag_patterns': [], 'unmeasured': 0, 'examples': [], 'example_total': 0,
            'bandwidth': {
                'full_count': 4, 'compared': 4,
                'publishing': ['bastet', 'gabelmoo'],
                'silent': ['faravahar', 'longclaw'],
                'scanners': ['bastet', 'faravahar', 'gabelmoo', 'longclaw'],
                'misses': [],
            },
        }
        text = self._render_block(vote_sum)
        assert "4 of 4 relays have Measured= published in the votes from all 2 of 4 publishing authorities" in text
        assert "no relays are missing Measured= from them." in text
        assert "No Measured= published in the votes from 2 of 4 authorities" in text
        assert "No relays are missing Measured= published in the votes from" not in text

    def test_partial_coverage_names_misses_and_silent_authorities(self):
        """When some relays lack Measured=, misses and silent authorities stay distinct."""
        vote_sum = {
            'agreed': 4, 'compared': 4, 'all_agreed': True, 'voters': ['bastet', 'gabelmoo'],
            'assigned_flags': FLAGS, 'absent_flags': [], 'split': 0, 'split_flags': [],
            'flag_patterns': [], 'unmeasured': 0, 'examples': [], 'example_total': 0,
            'bandwidth': {
                'full_count': 2, 'compared': 4,
                'publishing': ['bastet', 'gabelmoo'],
                'silent': ['faravahar', 'longclaw'],
                'scanners': ['bastet', 'faravahar', 'gabelmoo', 'longclaw'],
                'misses': [{'name': 'bastet', 'count': 2}],
            },
        }
        text = self._render_block(vote_sum)
        assert "2 of 4 relays have Measured= published in the votes from all 2 of 4 publishing authorities" in text
        assert "No Measured= published in the votes from 2 of 4 authorities" in text
        assert "bastet did not publish Measured= on 2 relays." in text

    def test_all_silent_authorities_are_reported_on_both_pages(self):
        from types import SimpleNamespace
        from allium.lib import page_writer

        vote_sum = {
            'compared': 1, 'agreed': 1, 'split': 0, 'unmeasured': 1, 'flag_rows': [],
            'bandwidth': {
                'full_count': 0, 'missing_count': 1, 'compared': 1, 'publishing': [],
                'silent': ['bastet', 'moria1'], 'scanners': ['bastet', 'moria1'], 'misses': [],
            },
        }
        text = self._render_block(vote_sum)
        assert 'Bandwidth measurements: No Measured= published in the votes from 2 of 2 authorities' in text
        assert 'bastet and moria1' in text
        assert 'publishing authorities' not in text

        env = page_writer.ENV
        source = env.loader.get_source(env, 'network-health-dashboard.html')[0]
        start = source.index('    {% if relays.vote_agreement_summary and relays.vote_agreement_summary.compared %}')
        end = source.index('    <!-- FIRST ROW -->', start)
        snippet = "{% from 'macros.html' import authority_list %}" + source[start:end]
        html = env.from_string(snippet).render(
            relays=SimpleNamespace(vote_agreement_summary=vote_sum),
            page_ctx=SimpleNamespace(path_prefix=''),
        )
        notice = html[html.index('<p class="vote-silent">'):].split('</p>', 1)[0]
        assert 'Not publishing Measured=:' in notice
        assert 'bastet' in notice and 'moria1' in notice
        assert 'Missing values by authority' not in html

    def test_dashboard_bandwidth_card_uses_missing_count_including_zeros(self):
        """Network health Bandwidth measurements card shows missing_count rather than measurement_split."""
        import re
        from types import SimpleNamespace
        from allium.lib import page_writer

        source = page_writer.ENV.loader.get_source(
            page_writer.ENV, 'network-health-dashboard.html'
        )[0]
        start = source.index('    {% if relays.vote_agreement_summary and relays.vote_agreement_summary.compared %}')
        end = source.index('\n    <!-- FIRST ROW -->', start)
        snippet = "{% from 'macros.html' import authority_list %}\n" + source[start:end]
        relays = SimpleNamespace(vote_agreement_summary={
            'compared': 3, 'agreed': 3, 'split': 0,
            'measurement_split': 1, 'unmeasured': 2, 'flag_rows': [],
            'bandwidth': {
                'full_count': 1, 'missing_count': 2, 'compared': 3,
                'publishing': ['bastet', 'moria1'],
                'silent': [], 'scanners': ['bastet', 'moria1'],
                'misses': [{'name': 'moria1', 'count': 2}, {'name': 'bastet', 'count': 1}],
            },
        })
        html = page_writer.ENV.from_string(snippet).render(
            relays=relays, page_ctx=SimpleNamespace(path_prefix='')
        )
        card = html[html.index('id="bandwidth-agreement"'):]
        match = re.search(
            r'<span class="metric-value">([^<]+)<sup[^>]*>.*?Relays missing Measured=',
            card, re.DOTALL,
        )
        assert match and match.group(1) == '2'

        relays_no_field = SimpleNamespace(vote_agreement_summary={
            'compared': 1, 'agreed': 1, 'split': 0,
            'measurement_split': 1, 'unmeasured': 1, 'flag_rows': [],
            'bandwidth': {
                'full_count': 0, 'compared': 1,
                'publishing': ['bastet'], 'silent': [], 'scanners': ['bastet'], 'misses': [],
            },
        })
        html_fallback = page_writer.ENV.from_string(snippet).render(
            relays=relays_no_field, page_ctx=SimpleNamespace(path_prefix='')
        )
        card_fallback = html_fallback[html_fallback.index('id="bandwidth-agreement"'):]
        match_fallback = re.search(
            r'<span class="metric-value">([^<]+)<sup[^>]*>.*?Relays missing Measured=',
            card_fallback, re.DOTALL,
        )
        assert match_fallback and match_fallback.group(1) == '0'
