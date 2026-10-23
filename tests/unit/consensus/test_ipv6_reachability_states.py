"""IPv6 reachability states from directory-authority vote documents.

dir-spec consensus-formats: an authority includes an ``a`` line only for an
IPv6 ORPort it found reachable. An authority whose vote contains any ``a``
line tests IPv6 (AuthDirHasIPv6Connectivity). Omitting the line is a failed
test only when the relay published an IPv6 ORPort. Onionoo or_addresses is
not that test.

Three states, plus the trap the operator cannot see today:
- tested-ok: ``a`` line present
- tested-failed: an IPv6-testing authority voted and omitted the ``a`` line
- not-tested: IPv6 ORPort published, and no vote contains a test
A single tester's omission stays failed even when every other authority does
not test IPv6.
"""

import base64

import pytest

from allium.lib.consensus.collector_fetcher import CollectorFetcher, ipv6_testers_from_collector
from allium.lib.consensus.consensus_evaluation import format_relay_consensus_evaluation
from allium.lib.ip_utils import relay_ipv6_unconfirmed, relay_publishes_ipv6
from allium.lib.relay_diagnostics import generate_issues_from_consensus

WITNESS = '11' * 20
OK_FP = 'AB' * 20
FAIL_FP = 'CD' * 20
UNTESTED_FP = 'EF' * 20
V4_FP = '12' * 20
# One IPv6-testing authority, eight that do not. Used to prove a real failure
# is not relabeled "not tested" when most authorities omit the 'a' line.
LONE_FP = '34' * 20

TESTERS = ['bastet', 'dannenberg', 'gabelmoo', 'longclaw', 'maatuska', 'moria1', 'tor26']
NON_TESTERS = ['dizum', 'faravahar']


def _identity(fingerprint):
    """Unpadded base64 identity, as a vote ``r`` line carries it."""
    return base64.b64encode(bytes.fromhex(fingerprint)).decode('ascii').rstrip('=')


def _relay_block(fingerprint, nickname, ipv6=None):
    lines = [
        'r {nickname} {identity} AAAAAAAAAAAAAAAAAAAAAAAAAAA '
        '2026-02-01 00:00:00 192.0.2.10 9001 0'.format(
            nickname=nickname, identity=_identity(fingerprint)),
    ]
    if ipv6:
        lines.append('a [{0}]:9001'.format(ipv6))
    lines.append('s Running Valid')
    lines.append('w Bandwidth=5000 Measured=4500')
    lines.append('stats wfu=0.99 tk=1000000 mtbf=2000000')
    return '\n'.join(lines)


def _vote_document(blocks):
    return '@type network-status-vote-3 1.0\n' + '\n'.join(blocks) + '\n'


def _load(votes_by_authority):
    """Parse fixture votes and index them the way a CollecTor fetch does."""
    fetcher = CollectorFetcher()
    fetcher.votes = {
        name: fetcher._parse_vote(document, 'AA' * 20)
        for name, document in votes_by_authority.items()
    }
    fetcher.bandwidth_files = {}
    fetcher._build_relay_index()
    return fetcher


def _evaluate(fetcher, fingerprint, published_ipv6, declared_unreachable=False):
    raw = fetcher.get_relay_consensus_evaluation(
        fingerprint, authority_count=9, published_ipv6=published_ipv6,
        declared_unreachable=declared_unreachable)
    formatted = format_relay_consensus_evaluation(raw, current_flags=['Running', 'Valid'])
    return raw, formatted


def _cells(formatted):
    return {row['authority']: row['ipv6_cell'] for row in formatted['authority_table']}


def _ipv6_rows(formatted):
    return [row for row in formatted['flag_requirements_table'] if row['metric'] == 'IPv6 Reachability']


def _titles(raw):
    return [issue['title'] for issue in generate_issues_from_consensus(raw, current_flags=['Running', 'Valid'])]


def _network_votes():
    """One hour of votes covering ok, failed, not-tested, and IPv4-only."""
    tester = _vote_document([
        _relay_block(WITNESS, 'Witness', ipv6='2001:db8::99'),
        _relay_block(OK_FP, 'OkRelay', ipv6='2001:db8::1'),
        _relay_block(FAIL_FP, 'FailRelay'),
        _relay_block(V4_FP, 'V4Only'),
    ])
    non_tester = _vote_document([
        _relay_block(OK_FP, 'OkRelay'),
        _relay_block(FAIL_FP, 'FailRelay'),
        _relay_block(UNTESTED_FP, 'Untested'),
        _relay_block(V4_FP, 'V4Only'),
    ])
    votes = {name: tester for name in TESTERS}
    votes.update({name: non_tester for name in NON_TESTERS})
    return votes


@pytest.fixture(scope='module')
def network():
    fetcher = _load(_network_votes())
    assert fetcher.ipv6_testing_authorities == set(TESTERS)
    return fetcher


class TestIpv6ReachabilityStates:
    def test_published_address_is_not_a_test(self):
        assert relay_publishes_ipv6(['192.0.2.1:9001', '[2001:db8::1]:9001']) is True
        assert relay_publishes_ipv6(['192.0.2.1:9001'], ['[2001:db8::2]:9001']) is True
        assert relay_publishes_ipv6(['192.0.2.1:9001']) is False
        assert relay_publishes_ipv6(None) is False

    def test_tested_ok_from_vote_a_line(self, network):
        raw, formatted = _evaluate(network, OK_FP, published_ipv6=True)
        reach = raw['reachability']
        summary = formatted['reachability_summary']['ipv6']

        assert reach['ipv6_state'] == 'ok'
        assert reach['ipv6_reachable_count'] == 7
        assert set(reach['ipv6_not_tested_authorities']) == set(NON_TESTERS)
        assert reach['ipv6_failed_authorities'] == []
        assert summary['state'] == 'ok'
        assert summary['display'] == '7/7 authorities can reach IPv6'
        assert summary['reachable_count'] == 7
        assert summary['total'] == 7
        assert summary['status_class'] == 'success'
        assert summary['show_ipv6'] is True

        row = _ipv6_rows(formatted)[0]
        assert row['status'] == 'meets'
        assert '7/7' in row['value']

        cells = _cells(formatted)
        assert cells['moria1'] == 'yes'
        assert cells['dizum'] == 'not_tested'
        assert 'IPv6 not reachable' not in _titles(raw)
        assert 'IPv6 not tested' not in _titles(raw)

    def test_tested_failed_stays_zero_of_n(self, network):
        raw, formatted = _evaluate(network, FAIL_FP, published_ipv6=True)
        reach = raw['reachability']
        summary = formatted['reachability_summary']['ipv6']

        assert reach['ipv6_state'] == 'failed'
        assert reach['ipv6_reachable_count'] == 0
        assert set(reach['ipv6_failed_authorities']) == set(TESTERS)
        assert summary['state'] == 'failed'
        assert summary['display'] == '0/7 authorities can reach IPv6'
        assert summary['status_class'] == 'danger'
        assert summary['show_ipv6'] is True
        assert 'Not tested' not in summary['display']

        row = _ipv6_rows(formatted)[0]
        assert row['status'] == 'below'
        assert '0/7' in row['value']

        cells = _cells(formatted)
        assert cells['moria1'] == 'no'
        assert cells['faravahar'] == 'not_tested'

        titles = _titles(raw)
        assert 'IPv6 not reachable' in titles
        assert 'IPv6 not tested' not in titles
        failure = next(issue for issue in generate_issues_from_consensus(raw) if issue['title'] == 'IPv6 not reachable')
        assert failure['severity'] == 'warning'
        assert failure['description'] == '0/7 authorities that test IPv6 can reach your IPv6 address'

    def test_not_tested_when_no_vote_contains_a_test(self, network):
        raw, formatted = _evaluate(network, UNTESTED_FP, published_ipv6=True)
        reach = raw['reachability']
        summary = formatted['reachability_summary']['ipv6']

        assert reach['ipv6_reachable_count'] == 0
        assert reach['ipv6_failed_authorities'] == []
        assert reach['ipv6_state'] == 'not_tested'
        assert summary['state'] == 'not_tested'
        assert summary['display'] == 'Not tested'
        assert summary['total'] == 0
        assert summary['show_ipv6'] is True
        assert summary['status_class'] == 'muted'

        row = _ipv6_rows(formatted)[0]
        assert row['status'] == 'not_tested'
        assert row['status_text'] == 'Not tested'
        assert row['value'] == 'Not tested'
        assert 'Below' not in row['status_text']

        cells = _cells(formatted)
        assert cells['dizum'] == 'not_tested'
        assert cells['moria1'] == 'absent'  # tester did not vote; that is not a failed test

        titles = _titles(raw)
        assert titles.count('IPv6 not tested') == 1
        assert 'IPv6 not reachable' not in titles
        note = next(issue for issue in generate_issues_from_consensus(raw) if issue['title'] == 'IPv6 not tested')
        assert note['severity'] == 'info'
        assert 'Allium does not run the check' in note['description']
        assert 'has not been found reachable' in note['description']

    def test_one_tester_omission_is_not_hidden_as_not_tested(self):
        """Eight authorities never test IPv6. The one that does voted without an ``a`` line."""
        tester = _vote_document([
            _relay_block(WITNESS, 'Witness', ipv6='2001:db8::99'),
            _relay_block(LONE_FP, 'LoneFail'),
        ])
        quiet = _vote_document([_relay_block(LONE_FP, 'LoneFail')])
        votes = {'moria1': tester}
        votes.update({name: quiet for name in NON_TESTERS + [n for n in TESTERS if n != 'moria1']})
        fetcher = _load(votes)
        assert fetcher.ipv6_testing_authorities == {'moria1'}

        raw, formatted = _evaluate(fetcher, LONE_FP, published_ipv6=True)
        summary = formatted['reachability_summary']['ipv6']

        assert raw['reachability']['ipv6_state'] == 'failed'
        assert raw['reachability']['ipv6_failed_authorities'] == ['moria1']
        assert summary['state'] == 'failed'
        assert summary['display'] == '0/1 authorities can reach IPv6'
        assert summary['show_ipv6'] is True
        assert _cells(formatted)['moria1'] == 'no'
        assert _cells(formatted)['dizum'] == 'not_tested'
        assert 'IPv6 not reachable' in _titles(raw)
        assert 'IPv6 not tested' not in _titles(raw)

    def test_omitted_a_line_without_published_ipv6_is_not_a_failure(self, network):
        raw, formatted = _evaluate(network, V4_FP, published_ipv6=False)
        summary = formatted['reachability_summary']['ipv6']

        assert raw['reachability']['ipv6_failed_authorities']  # testers voted, no 'a' line
        assert raw['reachability']['ipv6_state'] == 'none'
        assert summary['show_ipv6'] is False
        assert summary['state'] == 'none'
        assert summary['total'] == 0
        assert summary['display'] == 'None configured'
        assert _ipv6_rows(formatted) == []
        assert 'IPv6 not reachable' not in _titles(raw)
        assert 'IPv6 not tested' not in _titles(raw)

    def test_a_line_parses_as_reachable_and_marks_the_authority(self):
        fetcher = CollectorFetcher()
        with_a = fetcher._parse_vote(
            _vote_document([_relay_block(OK_FP, 'OkRelay', ipv6='2001:db8::5')]), 'AA' * 20)
        without_a = fetcher._parse_vote(
            _vote_document([_relay_block(OK_FP, 'OkRelay')]), 'BB' * 20)
        assert with_a['tests_ipv6'] is True
        assert without_a['tests_ipv6'] is False
        relay = next(iter(with_a['relays'].values()))
        assert relay['ipv6_reachable'] is True
        assert '2001:db8::5' in relay['ipv6_address']

    def test_non_voting_testers_are_not_in_the_denominator(self):
        """Five testers reached it. Two testers did not vote and do not count as tested."""
        voting_testers = TESTERS[:5]
        silent_testers = TESTERS[5:]
        tester_vote = _vote_document([
            _relay_block(WITNESS, 'Witness', ipv6='2001:db8::99'),
            _relay_block(OK_FP, 'OkRelay', ipv6='2001:db8::1'),
        ])
        non_tester_vote = _vote_document([_relay_block(OK_FP, 'OkRelay')])
        votes = {name: tester_vote for name in voting_testers}
        votes.update({name: non_tester_vote for name in NON_TESTERS})
        fetcher = _load(votes)
        assert fetcher.ipv6_testing_authorities == set(voting_testers)
        assert not (fetcher.ipv6_testing_authorities & set(silent_testers))
        raw, formatted = _evaluate(fetcher, OK_FP, published_ipv6=True)
        summary = formatted['reachability_summary']['ipv6']
        assert raw['reachability']['ipv6_tested_count'] == 5
        assert summary['display'] == '5/5 authorities can reach IPv6'
        assert summary['status_class'] == 'success'
        assert summary['total'] == 5

    def test_below_majority_is_not_full_success(self):
        """One of seven testing votes reached the relay. That is partial, not green."""
        reached = TESTERS[:1]
        missed = TESTERS[1:]
        reached_vote = _vote_document([
            _relay_block(WITNESS, 'Witness', ipv6='2001:db8::99'),
            _relay_block(OK_FP, 'OkRelay', ipv6='2001:db8::1'),
        ])
        missed_vote = _vote_document([
            _relay_block(WITNESS, 'Witness', ipv6='2001:db8::99'),
            _relay_block(OK_FP, 'OkRelay'),
        ])
        non_tester_vote = _vote_document([_relay_block(OK_FP, 'OkRelay')])
        votes = {reached[0]: reached_vote}
        votes.update({name: missed_vote for name in missed})
        votes.update({name: non_tester_vote for name in NON_TESTERS})
        fetcher = _load(votes)
        raw, formatted = _evaluate(fetcher, OK_FP, published_ipv6=True)
        summary = formatted['reachability_summary']['ipv6']
        assert summary['display'] == '1/7 authorities can reach IPv6'
        assert summary['status_class'] == 'warning'
        row = _ipv6_rows(formatted)[0]
        assert row['status'] == 'partial'

    def test_prior_tester_with_no_a_lines_is_still_a_failure(self):
        """A tester that reaches nobody this hour still has no 'a' line, and still tests."""
        votes = {
            name: _vote_document([_relay_block(LONE_FP, 'LoneFail')])
            for name in TESTERS + NON_TESTERS
        }
        fetcher = _load(votes)
        assert fetcher.ipv6_testing_authorities == set()
        fetcher.prior_ipv6_testing_authorities = {'moria1'}
        fetcher._build_relay_index()
        assert fetcher.ipv6_testing_authorities == {'moria1'}
        raw, formatted = _evaluate(fetcher, LONE_FP, published_ipv6=True)
        summary = formatted['reachability_summary']['ipv6']
        assert raw['reachability']['ipv6_state'] == 'failed'
        assert summary['display'] == '0/1 authorities can reach IPv6'
        assert summary['status_class'] == 'danger'
        assert 'IPv6 not tested' not in _titles(raw)
        assert 'IPv6 not reachable' in _titles(raw)

    def test_testers_recovered_from_relay_index(self):
        """A cache without ipv6_testing_authorities still records who published an 'a' line."""
        data = {
            'relay_index': {
                OK_FP: {'votes': {
                    'moria1': {'ipv6_reachable': True},
                    'dizum': {'ipv6_reachable': None},
                }},
            },
        }
        assert ipv6_testers_from_collector(data) == {'moria1'}
        assert ipv6_testers_from_collector({}) == set()
        assert ipv6_testers_from_collector({'ipv6_testing_authorities': ['tor26']}) == {'tor26'}

    def test_onionoo_unconfirmed_is_not_labeled_not_tested(self):
        """unreachable_or_addresses is a failed confirmation when no vote tested it."""
        assert relay_ipv6_unconfirmed(['[2001:db8::8]:9001']) is True
        assert relay_ipv6_unconfirmed(['192.0.2.8:9001']) is False
        votes = {
            name: _vote_document([_relay_block(UNTESTED_FP, 'Untested')])
            for name in TESTERS + NON_TESTERS
        }
        fetcher = _load(votes)
        raw, formatted = _evaluate(
            fetcher, UNTESTED_FP, published_ipv6=True, declared_unreachable=True)
        summary = formatted['reachability_summary']['ipv6']
        assert raw['reachability']['ipv6_state'] == 'failed'
        assert raw['reachability']['ipv6_failure_source'] == 'onionoo'
        assert summary['state'] == 'failed'
        assert summary['display'] == 'Unreachable'
        assert summary['status_class'] == 'danger'
        assert summary['show_ipv6'] is False
        row = _ipv6_rows(formatted)[0]
        assert row['status'] == 'below'
        assert row['status_text'] == 'Unreachable'
        titles = _titles(raw)
        assert 'IPv6 not reachable' in titles
        assert 'IPv6 not tested' not in titles
        failure = next(issue for issue in generate_issues_from_consensus(raw) if 'IPv6' in issue['title'])
        assert 'not confirmed' in failure['description']

    def test_a_line_wins_over_onionoo_unconfirmed(self, network):
        raw, formatted = _evaluate(network, OK_FP, published_ipv6=True, declared_unreachable=True)
        assert raw['reachability']['ipv6_state'] == 'ok'
        assert formatted['reachability_summary']['ipv6']['display'] == '7/7 authorities can reach IPv6'


def test_relay_pages_distinguish_the_three_states(network, tmp_path):
    """Rendered relay pages: Not tested is its own label, and 0/N stays a failure."""
    from jinja2 import Environment, FileSystemLoader

    from allium.lib import page_writer
    from allium.lib.relays import Relays

    def relay(fingerprint, nickname, addresses):
        return {
            'nickname': nickname,
            'fingerprint': fingerprint,
            'running': True,
            'observed_bandwidth': 1_000_000,
            'consensus_weight': 100,
            'flags': ['Running', 'Valid'],
            'first_seen': '2024-01-01 00:00:00',
            'last_seen': '2026-10-17 12:00:00',
            'last_restarted': '2026-10-01 00:00:00',
            'platform': 'Tor 0.4.8.10 on Linux',
            'country': 'de',
            'country_name': 'Germany',
            'as': 'AS100',
            'as_name': 'Example Networks',
            'or_addresses': addresses,
            'contact': '{0} <{0}@example.org>'.format(nickname),
            'effective_family': [fingerprint],
        }

    relay_set = Relays(
        output_dir=str(tmp_path),
        onionoo_url='https://onionoo.example.invalid/details',
        relay_data={
            'version': '8.0',
            'relays_published': '2026-10-17 12:00:00',
            'relays': [
                relay(OK_FP, 'OkRelay', ['192.0.2.1:9001', '[2001:db8::1]:9001']),
                relay(FAIL_FP, 'FailRelay', ['192.0.2.2:9001', '[2001:db8::2]:9001']),
                relay(UNTESTED_FP, 'Untested', ['192.0.2.3:9001', '[2001:db8::3]:9001']),
                relay(V4_FP, 'V4Only', ['192.0.2.4:9001']),
            ],
        },
        filter_downtime_days=0,
        mp_workers=0,
    )
    relay_set.enrich_with_api_data(collector_consensus_data={
        'relay_index': network.relay_index,
        'flag_thresholds': {},
        'bw_authorities': [],
        'ipv6_testing_authorities': sorted(network.ipv6_testing_authorities),
    })
    by_fp = {item['fingerprint']: item for item in relay_set.json['relays']}
    assert by_fp[OK_FP]['ipv6_authority_test'] == 'ok'
    assert by_fp[FAIL_FP]['ipv6_authority_test'] == 'failed'
    assert by_fp[UNTESTED_FP]['ipv6_authority_test'] == 'not_tested'
    assert by_fp[V4_FP]['ipv6_authority_test'] == ''

    page_writer.write_relay_info(relay_set)

    def html(fingerprint):
        return (tmp_path / 'relay' / fingerprint / 'index.html').read_text()

    ok_html = html(OK_FP)
    failed_html = html(FAIL_FP)
    untested_html = html(UNTESTED_FP)
    v4_html = html(V4_FP)

    assert '7/7' in ok_html
    assert '>Not tested<' not in ok_html
    assert '0/7' in failed_html
    assert '>Not tested<' not in failed_html
    assert 'IPv6 not reachable' in failed_html
    assert '>Not tested<' in untested_html
    assert 'IPv6 not tested' in untested_html
    assert 'IPv6 not reachable' not in untested_html
    assert '0/' not in untested_html.split('IPv6 Reachability', 1)[-1].split('</tr>', 1)[0]
    assert 'Allium does not run the check' in untested_html
    assert '>Not tested<' not in v4_html
    assert 'IPv6 not reachable' not in v4_html
    assert 'None configured' in v4_html
    assert '>0/7<' not in v4_html
    assert 'al-status-danger">0/7' in failed_html
    assert 'Suggestion:' in untested_html
    assert 'firewall' in untested_html

    env = Environment(loader=FileSystemLoader('allium/templates'))
    mark = env.from_string(
        '{% from "macros.html" import ipv6_test_mark %}'
        '{{ ipv6_test_mark(relay, compact=true) }}|'
        '{{ ipv6_test_mark(relay) }}'
    )
    compact = mark.render(relay={'ipv6_authority_test': 'not_tested'})
    list_mark, column_mark = compact.split('|')
    assert 'v6 N/T' in list_mark
    assert '>N/T<' in column_mark
    assert 'v6 N/T' not in column_mark
    failed_mark = mark.render(relay={'ipv6_authority_test': 'failed'})
    assert 'v6 Fail' in failed_mark.split('|')[0]
    assert 'v6 N/T' not in failed_mark
