"""Signal eligibility for overload status, diagnostics, counts, and charts.

Windows are applied to a fixed evaluation time. A report at 24 or 72 hours is
historical. Invalid and missing sources stay distinct from a confirmed
non-overloaded relay.
"""

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from allium.lib.bandwidth_utils import (
    apply_bandwidth_overload_fields,
    process_all_bandwidth_data_consolidated,
)
from allium.lib.charts.outcome import format_day
from allium.lib.charts.render import _overload_text
from allium.lib.contact_sorting import relay_sort_key
from allium.lib.network_health import calculate_network_health_metrics
from allium.lib.page_writer import write_relay_info
from allium.lib.relay_diagnostics import _check_overload_issues
from allium.lib.relays import Relays
from allium.lib.stability_utils import (
    FD_WINDOW_MS,
    GENERAL_WINDOW_MS,
    RATE_WINDOW_MS,
    compute_group_overload_summary,
    compute_relay_stability,
    evaluate_overload,
)

NOW = int(datetime(2026, 10, 16, 21, tzinfo=timezone.utc).timestamp())
NOW_MS = NOW * 1000
HOUR_MS = 3_600_000


def _status(relay, now=NOW):
    return compute_relay_stability(relay, now)


def _facts(relay, now=NOW):
    return _status(relay, now)['overload']


def test_reproduced_cases_at_the_reviewed_clock():
    """The four cases checked against compute_relay_stability on 2026-10-16."""
    rate = {'overload_ratelimits': {
        'timestamp': NOW_MS - 38 * HOUR_MS, 'write-count': 12, 'read-count': 25,
        'rate-limit': 1_000_000, 'burst-limit': 2_000_000,
    }}
    rate_status = _status(rate)
    assert rate_status['stability_is_overloaded'] is False
    assert rate_status['overload']['rate']['state'] == 'historical'

    fd_status = _status({'overload_fd_exhausted': {'timestamp': NOW_MS - 96 * HOUR_MS}})
    assert fd_status['stability_is_overloaded'] is False
    assert fd_status['overload']['fd']['state'] == 'historical'

    future = _status({'overload_general_timestamp': NOW_MS + HOUR_MS})
    assert future['stability_is_overloaded'] is False
    assert future['stability_text'] == 'Incomplete'
    assert future['overload']['general']['state'] == 'invalid'

    recent = _status({'overload_general_timestamp': NOW_MS - HOUR_MS})
    assert recent['stability_is_overloaded'] is True
    assert recent['stability_text'] == 'Overloaded'
    assert 'General overload at ' in recent['stability_tooltip']


@pytest.mark.parametrize('window_ms,field,payload', [
    (GENERAL_WINDOW_MS, 'general', lambda ts: {'overload_general_timestamp': ts}),
    (FD_WINDOW_MS, 'fd', lambda ts: {'overload_fd_exhausted': {'timestamp': ts}}),
    (RATE_WINDOW_MS, 'rate', lambda ts: {'overload_ratelimits': {
        'timestamp': ts, 'write-count': 4, 'read-count': 0}}),
])
def test_windows_just_inside_at_and_outside(window_ms, field, payload):
    inside = _facts(payload(NOW_MS - window_ms + 1))
    exact = _facts(payload(NOW_MS - window_ms))
    outside = _facts(payload(NOW_MS - window_ms - 1))
    assert inside[field]['state'] == 'eligible'
    assert inside['is_overloaded'] is True
    assert exact[field]['state'] == 'historical'
    assert exact['is_overloaded'] is False
    assert outside[field]['state'] == 'historical'
    assert outside['is_overloaded'] is False
    assert exact[field]['when']  # the cutoff timestamp is kept for display


@pytest.mark.parametrize('bad', [
    0, -1, -HOUR_MS, True, False, '1700000000000', float('nan'), float('inf'),
    float('-inf'), 10 ** 30, [], {},
])
def test_bad_timestamps_are_invalid_and_do_not_overload(bad):
    for relay in (
        {'overload_general_timestamp': bad},
        {'overload_fd_exhausted': {'timestamp': bad}},
        {'overload_ratelimits': {'timestamp': bad, 'write-count': 9, 'read-count': 9}},
    ):
        facts = evaluate_overload(relay, NOW)
        assert facts['is_overloaded'] is False
        signal = next(facts[name] for name in ('general', 'rate', 'fd') if facts[name]['state'] != 'absent')
        assert signal['state'] == 'invalid'


def test_empty_and_non_dict_records_are_invalid():
    empty_fd = evaluate_overload({'overload_fd_exhausted': {}}, NOW)
    assert empty_fd['fd']['state'] == 'invalid'
    assert empty_fd['is_overloaded'] is False
    for bad in ('yes', ['timestamp'], 1):
        facts = evaluate_overload({
            'overload_fd_exhausted': bad,
            'overload_ratelimits': bad,
        }, NOW)
        assert facts['fd']['state'] == 'invalid'
        assert facts['rate']['state'] == 'invalid'
        assert facts['is_overloaded'] is False


def test_rate_counts_and_missing_configuration():
    recent = NOW_MS - HOUR_MS
    zero = _facts({'overload_ratelimits': {
        'timestamp': recent, 'write-count': 0, 'read-count': 0,
        'rate-limit': 1000, 'burst-limit': 2000,
    }})
    assert zero['rate']['state'] == 'zero'
    assert zero['rate']['status_label'] == 'No rate-limit hits reported'
    assert zero['is_overloaded'] is False
    assert zero['headline'] == 'clear'

    one_side = _facts({'overload_ratelimits': {
        'timestamp': recent, 'write-count': 12, 'read-count': 0,
    }})
    assert one_side['is_overloaded'] is True
    assert one_side['rate']['rate_display'] == 'unavailable'
    assert one_side['rate']['burst_display'] == 'unavailable'
    assert one_side['rate']['write_display'] == '12'
    assert one_side['rate']['read_display'] == '0'
    assert 'limit: unavailable' in _status({'overload_ratelimits': {
        'timestamp': recent, 'write-count': 12, 'read-count': 0,
    }})['stability_tooltip']
    from allium.lib.bandwidth_formatter import BandwidthFormatter
    bits = compute_relay_stability({'overload_ratelimits': {
        'timestamp': recent, 'write-count': 12, 'read-count': 0, 'rate-limit': 1_000_000,
    }}, NOW, BandwidthFormatter(use_bits=True))
    assert 'Mbit/s' in bits['stability_tooltip']
    assert 'Mbit/s' in bits['overload']['rate']['rate_display']
    assert bits['overload']['rate']['burst_display'] == 'unavailable'

    partial = _facts({'overload_ratelimits': {
        'timestamp': recent, 'write-count': 12, 'read-count': 'nope',
        'rate-limit': 'fast', 'burst-limit': None,
    }})
    assert partial['is_overloaded'] is True
    assert partial['rate']['read_display'] == 'unknown'
    assert partial['rate']['read_display'] != '0'
    assert partial['rate']['rate_display'] == 'unavailable'

    not_a_zero = _facts({'overload_ratelimits': {
        'timestamp': recent, 'write-count': 0, 'read-count': True,
    }})
    assert not_a_zero['rate']['state'] == 'invalid'
    assert not_a_zero['rate']['status_label'] != 'No rate-limit hits reported'
    assert not_a_zero['headline'] == 'incomplete'
    assert not_a_zero['is_overloaded'] is False

    for bad_count in (-1, '12', float('nan'), 1.5, False):
        facts = evaluate_overload({'overload_ratelimits': {
            'timestamp': recent, 'write-count': bad_count, 'read-count': bad_count,
        }}, NOW)
        assert facts['is_overloaded'] is False
        assert facts['rate']['state'] == 'invalid'


def test_valid_signal_survives_an_invalid_or_expired_companion():
    relay = {
        'overload_general_timestamp': NOW_MS - HOUR_MS,
        'overload_fd_exhausted': {},
        'overload_ratelimits': {
            'timestamp': NOW_MS - 30 * HOUR_MS, 'write-count': 40, 'read-count': 1,
        },
    }
    facts = _facts(relay)
    assert facts['is_overloaded'] is True
    assert facts['general']['state'] == 'eligible'
    assert facts['fd']['state'] == 'invalid'
    assert facts['rate']['state'] == 'historical'
    assert facts['fd']['status_label'] == 'Invalid overload data'
    issues = _check_overload_issues(relay, facts=facts)
    titles = [issue['title'] for issue in issues]
    assert titles == ['General Overload Active']


def test_newer_ineligible_record_does_not_replace_the_eligible_timestamp():
    fd_ms = NOW_MS - 70 * HOUR_MS
    relay = {
        'running': True,
        'overload_fd_exhausted': {'timestamp': fd_ms},
        'overload_ratelimits': {
            'timestamp': NOW_MS - 25 * HOUR_MS, 'write-count': 8, 'read-count': 0,
        },
    }
    status = _status(relay)
    facts = status['overload']
    assert facts['latest_eligible_ms'] == fd_ms
    relay.update(status)
    last = datetime.fromtimestamp(fd_ms / 1000, tz=timezone.utc)
    expected = 'currently overloaded · last report {}, {:%H:%M} UTC'.format(format_day(last), last)
    assert _overload_text(relay) == expected

    zero_newer = {
        'running': True,
        'overload_fd_exhausted': {'timestamp': fd_ms},
        'overload_ratelimits': {
            'timestamp': NOW_MS - HOUR_MS, 'write-count': 0, 'read-count': 0,
        },
    }
    zero_status = _status(zero_newer)
    assert zero_status['overload']['latest_eligible_ms'] == fd_ms
    assert zero_status['overload']['rate']['state'] == 'zero'

    invalid_newer = _facts({
        'overload_general_timestamp': NOW_MS - 10 * HOUR_MS,
        'overload_fd_exhausted': {'timestamp': NOW_MS + HOUR_MS},
    })
    assert invalid_newer['latest_eligible_ms'] == NOW_MS - 10 * HOUR_MS
    assert invalid_newer['fd']['state'] == 'invalid'


def test_source_availability_is_not_inferred_from_truthiness():
    loaded_absent = {'fingerprint': 'A' * 40}
    apply_bandwidth_overload_fields([loaded_absent], {
        'relays_published': '2026-10-16 18:00:00',
        'relays': [{'fingerprint': 'A' * 40, 'read_history': {}}],
    })
    absent = evaluate_overload(loaded_absent, NOW)
    assert absent['headline'] == 'clear'
    assert absent['rate']['status_label'] == 'No rate-limit report in available data'
    assert absent['fd']['status_label'] == 'No file-descriptor exhaustion report in available data'

    missing = {'fingerprint': 'B' * 40, 'overload_ratelimits': {'write-count': 5}}
    apply_bandwidth_overload_fields([missing], {
        'relays': [{'fingerprint': 'A' * 40}],
    })
    no_record = evaluate_overload(missing, NOW)
    assert 'overload_ratelimits' not in missing
    assert no_record['rate']['status_label'] == 'No bandwidth record available for this relay'
    assert no_record['headline'] == 'incomplete'
    assert no_record['is_overloaded'] is False

    offline = {'fingerprint': 'C' * 40, 'overload_fd_exhausted': {'timestamp': NOW_MS - HOUR_MS}}
    apply_bandwidth_overload_fields([offline], None)
    unavailable = evaluate_overload(offline, NOW)
    assert 'overload_fd_exhausted' not in offline
    assert unavailable['fd']['status_label'] == 'Bandwidth data unavailable'
    assert unavailable['headline'] == 'incomplete'


def test_repeated_enrichment_drops_stale_overload_fields():
    relay = {'fingerprint': 'A' * 40, 'overload_ratelimits': {'timestamp': NOW_MS, 'write-count': 3,
                                                               'read-count': 1},
             'overload_fd_exhausted': {'timestamp': NOW_MS}}
    document = {'relays': [{'fingerprint': 'A' * 40, 'overload_ratelimits': {},
                            'read_history': {}}]}
    apply_bandwidth_overload_fields([relay], document)
    assert relay['overload_ratelimits'] == {}
    assert 'overload_fd_exhausted' not in relay
    assert evaluate_overload(relay, NOW)['is_overloaded'] is False

    apply_bandwidth_overload_fields([relay], {'relays': [{'fingerprint': 'A' * 40}]})
    assert 'overload_ratelimits' not in relay
    assert evaluate_overload(relay, NOW)['rate']['state'] == 'absent'


def test_bandwidth_processor_keeps_present_but_falsey_overload_values():
    relays = [{'fingerprint': 'A' * 40, 'flags': []}]
    payload = {'relays': [
        {'fingerprint': 'A' * 40, 'overload_ratelimits': {}, 'overload_fd_exhausted': None},
        {'fingerprint': 'B' * 40},
    ]}
    processed = process_all_bandwidth_data_consolidated(relays, payload, include_flag_analysis=False)
    row = processed['relay_bandwidth_data']['A' * 40]
    assert row['overload_ratelimits_present'] is True
    assert row['overload_ratelimits'] == {}
    assert row['overload_fd_exhausted_present'] is True
    assert row['overload_fd_exhausted'] is None
    other = processed['relay_bandwidth_data']['B' * 40]
    assert other['overload_ratelimits_present'] is False
    assert other['overload_fd_exhausted_present'] is False


def test_preserved_operator_strings_and_removed_claims():
    diagnostics = Path('allium/lib/relay_diagnostics.py').read_text(encoding='utf-8')
    template = Path('allium/templates/relay-info.html').read_text(encoding='utf-8')
    macros = Path('allium/templates/macros.html').read_text(encoding='utf-8')
    guidance = Path('allium/lib/stability_utils.py').read_text(encoding='utf-8')
    assert "title': 'General Overload Active'" in diagnostics
    assert '[Warning] OVERLOADED' in template
    assert 'currently flagged as overloaded' in macros
    for text in (diagnostics, template, guidance):
        assert 'OOM killer' not in text
        assert 'Check if ISP is throttling' not in text
        assert 'ulimit -n' not in text
    assert 'is not evidence of ISP throttling' in guidance
    for anchor in ('id="overload"', 'id="overload-general"', 'id="overload-fd"',
                   'id="overload-write"', 'id="overload-read"', 'id="overload-rate-config"'):
        assert anchor in template


def _member(fingerprint, nickname, bandwidth, **extra):
    relay = {
        'nickname': nickname,
        'fingerprint': fingerprint,
        'running': True,
        'observed_bandwidth': bandwidth,
        'consensus_weight': 100,
        'flags': ['Running', 'Valid', 'Fast'],
        'first_seen': '2024-01-01 00:00:00',
        'last_seen': '2026-10-16 21:00:00',
        'last_restarted': '2026-10-01 00:00:00',
        'platform': 'Tor 0.4.8.12 on Linux',
        'version': '0.4.8.12',
        'recommended_version': True,
        'country': 'de',
        'country_name': 'Germany',
        'as': 'AS100',
        'as_name': 'Example Networks',
        'or_addresses': ['192.0.2.1:9001'],
        'contact': 'operator <op@example.org>',
        'effective_family': [fingerprint],
    }
    relay.update(extra)
    return relay


def _build(tmp_path, relays, bandwidth=None, collector=None):
    relay_set = Relays(
        output_dir=str(tmp_path),
        onionoo_url='https://onionoo.example.invalid/details',
        relay_data={
            'version': '8.0',
            'relays_published': '2026-10-16 20:00:00',
            'relays': relays,
        },
        filter_downtime_days=0,
        mp_workers=0,
    )
    relay_set.enrich_with_api_data(
        bandwidth_data=bandwidth, collector_consensus_data=collector)
    return relay_set


def _by_fp(relay_set):
    return {relay['fingerprint']: relay for relay in relay_set.json['relays']}


def test_details_only_and_bandwidth_history_failure(tmp_path, monkeypatch):
    recent = int(time.time() * 1000) - HOUR_MS
    general_fp = '1' * 40
    quiet_fp = '2' * 40
    relays = [
        _member(general_fp, 'general', 2_000_000, overload_general_timestamp=recent),
        _member(quiet_fp, 'quiet', 1_000_000),
    ]
    details_only = _build(tmp_path / 'details', relays, bandwidth=None)
    found = _by_fp(details_only)
    assert found[general_fp]['stability_is_overloaded'] is True
    assert found[general_fp]['overload']['rate']['status_label'] == 'Bandwidth data unavailable'
    assert found[general_fp]['diagnostics']['issues'][0]['title'] == 'General Overload Active'
    assert found[quiet_fp]['stability_text'] == 'Incomplete'
    assert found[quiet_fp]['stability_is_overloaded'] is False
    assert 'Not Overloaded' not in found[quiet_fp]['stability_text']

    def _boom(*_args, **_kwargs):
        raise RuntimeError('history failed')

    monkeypatch.setattr(
        'allium.lib.bandwidth_utils.process_all_bandwidth_data_consolidated', _boom)
    fd_fp = '3' * 40
    failed = _build(tmp_path / 'failed', [
        _member(general_fp, 'general', 2_000_000, overload_general_timestamp=recent),
        _member(fd_fp, 'fdonly', 1_000_000),
    ], bandwidth={
        'relays_published': '2026-10-16 18:00:00',
        'relays': [
            {'fingerprint': general_fp},
            {'fingerprint': fd_fp, 'overload_fd_exhausted': {'timestamp': recent}},
        ],
    })
    failed_relays = _by_fp(failed)
    assert failed_relays[general_fp]['stability_is_overloaded'] is True
    assert failed_relays[fd_fp]['overload']['fd']['state'] == 'eligible'
    assert failed_relays[fd_fp]['stability_is_overloaded'] is True


def test_collector_does_not_duplicate_overload_diagnostics(tmp_path):
    recent = int(time.time() * 1000) - HOUR_MS
    fingerprint = '4' * 40
    other = '5' * 40
    collector = {
        'relay_index': {other: {'votes': {}}},
        'flag_thresholds': {'moria1': {}},
        'bw_authorities': [],
    }
    relay_set = _build(tmp_path, [
        _member(fingerprint, 'flagged', 1_000_000, overload_general_timestamp=recent),
    ], collector=collector)
    relay = relay_set.json['relays'][0]
    titles = [issue['title'] for issue in relay['diagnostics']['issues']]
    assert titles.count('General Overload Active') == 1

    relay_set._reprocess_collector_data()
    titles = [issue['title'] for issue in relay['diagnostics']['issues']]
    assert titles.count('General Overload Active') == 1

    no_collector = _build(tmp_path / 'noc', [
        _member(fingerprint, 'flagged', 1_000_000, overload_general_timestamp=recent),
    ])
    alone = [issue['title'] for issue in no_collector.json['relays'][0]['diagnostics']['issues']]
    assert alone.count('General Overload Active') == 1


def test_consumers_agree_and_pages_render_each_state(tmp_path):
    recent = int((time.time() - 3600) * 1000)
    old = int((time.time() - 96 * 3600) * 1000)
    fps = {
        'general': 'a' * 40,
        'rate': 'b' * 40,
        'fd': 'c' * 40,
        'partial': 'd' * 40,
        'historical': 'e' * 40,
        'missing': 'f' * 40,
    }
    relays = [
        _member(fps['general'], 'general', 6_000_000, overload_general_timestamp=recent),
        _member(fps['rate'], 'rate', 5_000_000),
        _member(fps['fd'], 'fd', 4_000_000),
        _member(fps['partial'], 'partial', 3_000_000),
        _member(fps['historical'], 'historical', 2_000_000, overload_general_timestamp=old),
        _member(fps['missing'], 'missing', 1_000_000),
    ]
    bandwidth = {
        'relays_published': '2026-10-16 18:00:00',
        'relays': [
            {'fingerprint': fps['general']},
            {'fingerprint': fps['rate'], 'overload_ratelimits': {
                'timestamp': recent, 'write-count': 12, 'read-count': 0,
                'rate-limit': 1_000_000, 'burst-limit': 2_000_000,
            }},
            {'fingerprint': fps['fd'], 'overload_fd_exhausted': {'timestamp': recent}},
            {'fingerprint': fps['partial'], 'overload_ratelimits': {
                'timestamp': recent, 'write-count': 7, 'read-count': 'bad',
            }},
            {'fingerprint': fps['historical']},
        ],
    }
    relay_set = _build(tmp_path, relays, bandwidth=bandwidth)
    found = _by_fp(relay_set)

    overloaded = {fps['general'], fps['rate'], fps['fd'], fps['partial']}
    assert {fp for fp, relay in found.items() if relay['stability_is_overloaded']} == overloaded
    assert found[fps['historical']]['stability_text'] == 'Not Overloaded'
    assert found[fps['historical']]['overload']['general']['state'] == 'historical'
    assert found[fps['missing']]['stability_text'] == 'Incomplete'
    assert found[fps['missing']]['overload']['rate']['status_label'] == (
        'No bandwidth record available for this relay')
    assert found[fps['partial']]['overload']['rate']['read_display'] == 'unknown'

    calculate_network_health_metrics(relay_set)
    assert relay_set.json['network_health']['overloaded_relays'] == 4

    members = list(found.values())
    summary = compute_group_overload_summary(members)
    assert summary['overloaded'] == 4
    ordered = sorted(members, key=lambda relay: relay_sort_key(relay, 'overload'))
    assert [relay['fingerprint'] for relay in ordered[:4]] == [
        fps['general'], fps['rate'], fps['fd'], fps['partial']]

    for fingerprint in overloaded:
        relay = found[fingerprint]
        issues = [issue for issue in relay['diagnostics']['issues'] if issue['category'] == 'overload'
                  and issue['severity'] != 'info']
        assert issues
        caption = _overload_text(relay)
        assert caption.startswith('currently overloaded')
        stamp = relay['overload']['latest_eligible_ms']
        last = datetime.fromtimestamp(stamp / 1000, tz=timezone.utc)
        assert '{:%H:%M}'.format(last) in caption
        # Diagnostics were built from the same fact record as the caption.
        again = _check_overload_issues(relay, facts=relay['overload'])
        assert [issue['title'] for issue in again] == [
            issue['title'] for issue in relay['diagnostics']['issues'] if issue['category'] == 'overload']

    # A historical general report inside a week is an info note, not an overload.
    historical_titles = [issue['title'] for issue in found[fps['historical']]['diagnostics']['issues']]
    assert historical_titles == ['Recent Overload Reported']
    assert _overload_text(found[fps['historical']]) is None

    write_relay_info(relay_set)
    from tests.helpers.html_links import dead_fragment_links
    assert dead_fragment_links(tmp_path) == []
    pages = {}
    anchors = ('id="overload"', 'id="overload-general"', 'id="overload-fd"',
               'id="overload-write"', 'id="overload-read"', 'id="overload-rate-config"')
    for name, fingerprint in fps.items():
        html = (tmp_path / 'relay' / fingerprint / 'index.html').read_text(encoding='utf-8')
        pages[name] = html
        for anchor in anchors:
            assert anchor in html, (name, anchor)
        assert 'OOM killer' not in html
        assert 'Check if ISP is throttling' not in html
        assert 'ulimit -n' not in html
        assert 'curl http://127.0.0.1:9035/metrics' in html

    assert '[Warning] OVERLOADED' in pages['general']
    assert 'General Overload Active' in pages['general']
    assert 'tor_relay_load_oom_bytes_total' in pages['general']
    assert 'tor_relay_load_onionskins_total' in pages['general']
    assert 'tor_relay_load_tcp_exhaustion_total' in pages['general']
    assert 'href="#overload-general"' in pages['general']
    assert 'hour precision' in pages['general']

    assert 'Write Bandwidth Limit Hit' in pages['rate']
    assert 'tor_relay_load_global_rate_limit_reached_total' in pages['rate']
    assert 'href="#overload-write"' in pages['rate']
    assert 'href="#overload-rate-config"' in pages['rate']
    assert '>12<' in pages['rate'] or '12' in pages['rate']

    assert 'File Descriptor Exhaustion' in pages['fd']
    assert 'LimitNOFILE' in pages['fd']
    assert 'tor_relay_load_socket_total{state="opened"}' in pages['fd']
    assert 'state="max"' not in pages['fd']
    assert 'href="#overload-fd"' in pages['fd']

    assert 'unknown' in pages['partial']
    assert 'read_display' not in pages['partial']
    partial_read = pages['partial'].split('id="overload-read"', 1)[1].split('</dd>', 1)[0]
    assert 'unknown' in partial_read
    assert '>0<' not in partial_read

    assert 'Not Overloaded' in pages['historical']
    assert '[Warning] OVERLOADED' not in pages['historical']
    assert 'Historical report — outside the 72-hour window' in pages['historical']
    assert 'href="#overload-general"' in pages['historical']

    assert 'Incomplete' in pages['missing']
    assert 'No bandwidth record available for this relay' in pages['missing']
    assert 'Not Overloaded' not in pages['missing']

    excerpt_dir = Path('/opt/cursor/artifacts')
    if excerpt_dir.is_dir():
        for name in ('general', 'rate', 'fd', 'partial', 'historical', 'missing'):
            html = pages[name]
            start = html.index('id="overload"')
            end = html.index('id="operator"')
            (excerpt_dir / f'overload-{name}.html').write_text(html[start:end], encoding='utf-8')
