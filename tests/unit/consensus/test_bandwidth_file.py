"""Bandwidth-file digest selection and scanner rows. No network."""

import base64

from jinja2 import Environment, FileSystemLoader, select_autoescape

from allium.lib.consensus.collector_fetcher import (
    CollectorFetcher,
    bandwidth_digest_hex,
    format_scanner_measurements,
    select_bandwidth_filenames,
)

FP = 'A' * 40
DIGEST_B64 = '4j+nI5ddEzuniXastOiPrZLWR4SePgRml50OpR5Q8kw'
DIGEST_HEX = base64.b64decode(DIGEST_B64 + '=').hex().upper()


def _file(scanner, country, relays, created='2026-10-24T04:45:06'):
    header = (
        '@type bandwidth-file 1.0\n'
        '1792816834\n'
        'version=1.9.0\n'
        'dirauth_nickname=%s\n'
        'scanner_country=%s\n'
        'file_created=%s\n'
    ) % (scanner, country, created)
    lines = [header.rstrip('\n')]
    for fingerprint, fields in relays:
        parts = ['bw=%s' % fields['bw'], 'node_id=%s' % fingerprint]
        for key in ('bw_mean', 'bw_median', 'rtt', 'desc_bw_obs_last', 'error_stream', 'success'):
            if key in fields:
                parts.append('%s=%s' % (key, fields[key]))
        if fields.get('time'):
            parts.append('time=%s' % fields['time'])
        lines.append(' '.join(parts))
    return '\n'.join(lines) + '\n'


class TestBandwidthDigest:
    def test_vote_digest_matches_collector_filename_hex(self):
        line = 'bandwidth-file-digest sha256=%s' % DIGEST_B64
        assert bandwidth_digest_hex(line) == DIGEST_HEX

    def test_junk_digest_is_ignored(self):
        assert bandwidth_digest_hex('bandwidth-file-digest sha256=!!!!') is None
        assert bandwidth_digest_hex('no digest here') is None

    def test_selects_the_vote_file_not_the_newest_name(self):
        newest = '2026-10-24-09-00-00-bandwidth-' + ('B' * 64)
        named = '2026-10-24-06-00-00-bandwidth-' + DIGEST_HEX
        chosen = select_bandwidth_filenames([newest, named], [DIGEST_HEX])
        assert chosen == [named]

    def test_without_a_digest_uses_the_newest_file(self):
        older = '2026-10-20-01-00-00-bandwidth-' + ('A' * 64)
        newer = '2026-10-24-01-00-00-bandwidth-' + ('C' * 64)
        assert select_bandwidth_filenames([older, newer], []) == [newer]

    def test_a_requested_digest_that_misses_does_not_use_the_newest_file(self):
        newest = '2026-10-24-09-00-00-bandwidth-' + ('F' * 64)
        assert select_bandwidth_filenames([newest], ['B' * 64]) == []

    def test_last_valid_digest_token_wins(self):
        real = 'sha256=%s' % DIGEST_B64
        line = 'bandwidth-file-digest sha256=%s %s' % ('A' * 43, real)
        assert bandwidth_digest_hex(line) == DIGEST_HEX
        assert bandwidth_digest_hex('sha256=%s=AAAA' % DIGEST_B64) is None

    def test_parse_vote_keeps_the_digest(self):
        content = (
            'network-status-version 3\n'
            'vote-status vote\n'
            'bandwidth-file-headers timestamp=1 dirauth_nickname=moria1\n'
            'bandwidth-file-digest sha256=%s\n'
            'r Test AAAAAAAAAAAAAAAAAAAAAAAAAAA 2026-10-24 05:00:00 1.2.3.4 9001 0\n'
        ) % DIGEST_B64
        # r line is too short to become a relay; the digest is a header field.
        vote = CollectorFetcher()._parse_vote(content, 'F' * 40)
        assert vote['has_bandwidth_file_headers'] is True
        assert vote['bandwidth_file_digest'] == DIGEST_HEX


class TestBandwidthDownload:
    def test_merges_one_row_per_scanner(self, monkeypatch):
        bastet = _file('bastet', 'US', [(FP, {
            'bw': 10, 'rtt': 15, 'time': '2026-10-24T01:00:00',
        })])
        moria = _file('moria1', 'US', [(FP, {
            'bw': 30, 'time': '2026-10-24T02:00:00',
        })])
        names = {
            '2026-10-24-01-00-00-bandwidth-' + ('A' * 64): bastet,
            '2026-10-24-02-00-00-bandwidth-' + ('B' * 64): moria,
            '2026-10-24-03-00-00-bandwidth-' + ('C' * 64): 'bw=999 node_id=%s\n' % ('D' * 40),
        }
        fetcher = CollectorFetcher()
        monkeypatch.setattr(fetcher, '_fetch_url', lambda url: names[url.rsplit('/', 1)[-1]])
        merged = fetcher._download_bandwidth_files(list(names), ['A' * 64, 'B' * 64])
        scanners = [row['scanner'] for row in merged[FP]['scanners']]
        assert scanners == ['bastet', 'moria1']
        assert merged[FP]['scanners'][0]['rtt'] == 15
        assert 'D' * 40 not in merged


class TestBandwidthFileRows:
    def test_superscript_digit_does_not_abort_the_file(self):
        body = 'dirauth_nickname=moria1\nbw=² node_id=%s\nbw=4 node_id=%s\n' % (FP, 'B' * 40)
        parsed = CollectorFetcher()._parse_bandwidth_file(body)
        assert FP not in parsed
        assert parsed['B' * 40]['bw'] == 4

    def test_parses_bare_node_id_rtt_and_omitted_rtt(self):
        fetcher = CollectorFetcher()
        with_rtt = _file('bastet', 'US', [(
            '$' + FP.lower(),
            {
                'bw': 50, 'bw_mean': 48, 'bw_median': 49, 'rtt': 42,
                'desc_bw_obs_last': 33767, 'error_stream': 1, 'success': 9,
                'time': '2026-10-23T08:32:09',
            },
        )])
        other = 'B' * 40
        without_rtt = _file('longclaw', 'DE', [(
            other,
            {'bw': 1, 'bw_mean': 11043, 'bw_median': 11584, 'time': '2026-10-23T09:00:00'},
        )])
        bastet = fetcher._parse_bandwidth_file(with_rtt)
        longclaw = fetcher._parse_bandwidth_file(without_rtt)
        assert bastet[FP]['scanner'] == 'bastet'
        assert bastet[FP]['rtt'] == 42
        assert bastet[FP]['obs_last'] == 33767
        assert 'rtt' not in longclaw[other]
        merged = {
            FP: {'scanners': [bastet[FP]]},
            other: {'scanners': [longclaw[other]]},
        }
        shown = format_scanner_measurements(merged[FP], use_bits=False)
        assert shown['any_rtt'] is True
        assert shown['rows'][0]['rtt_display'] == '42 ms'
        assert shown['rows'][0]['scanner'] == 'bastet'
        assert 'KB/s' in shown['rows'][0]['bw_display'] or 'B/s' in shown['rows'][0]['bw_display']
        quiet = format_scanner_measurements(merged[other], use_bits=False)
        assert quiet['any_rtt'] is False
        assert quiet['rows'][0]['rtt_display'] == '—'
        assert quiet['rows'][0]['streams'] == '—'

    def test_mean_and_median_are_bytes_and_bw_is_kilobytes(self):
        # sbws 1.9: bw is divided down to KB/s; bw_mean and bw_median stay bytes/s.
        shown = format_scanner_measurements({
            'scanners': [{
                'scanner': 'gabelmoo',
                'bw': 2,
                'bw_mean': 52204,
                'bw_median': 56169,
                'obs_last': 724992,
                'rtt': 15.0,
            }],
        }, use_bits=False)
        row = shown['rows'][0]
        assert row['bw_display'] == '2.0 KB/s'
        assert row['mean_display'] == '52.2 KB/s'
        assert row['median_display'] == '56.2 KB/s'
        assert row['obs_display'] == '725.0 KB/s'
        assert row['rtt_display'] == '15 ms'
        assert shown['any_rtt'] is True

    def test_node_id_before_bw_and_later_nickname_does_not_relabel(self):
        body = (
            'dirauth_nickname=gabelmoo\n'
            'node_id=%s bw=2\n'
            'dirauth_nickname=longclaw\n'
            'bw=9 node_id=%s\n'
        ) % (FP, 'B' * 40)
        parsed = CollectorFetcher()._parse_bandwidth_file(body)
        assert parsed[FP]['scanner'] == 'gabelmoo'
        assert parsed[FP]['bw'] == 2
        assert parsed['B' * 40]['scanner'] == 'gabelmoo'
        assert parsed['B' * 40]['bw'] == 9

    def test_same_scanner_keeps_the_later_filename(self, monkeypatch):
        early = _file('gabelmoo', 'DE', [(FP, {'bw': 1})])
        late = _file('gabelmoo', 'DE', [(FP, {'bw': 99})])
        names = {
            '2026-10-24-01-00-00-bandwidth-' + ('A' * 64): early,
            '2026-10-24-02-00-00-bandwidth-' + ('B' * 64): late,
        }
        fetcher = CollectorFetcher()
        monkeypatch.setattr(fetcher, '_fetch_url', lambda url: names[url.rsplit('/', 1)[-1]])
        merged = fetcher._download_bandwidth_files(
            list(names), ['A' * 64, 'B' * 64])
        assert merged[FP]['scanners'][0]['bw'] == 99
        assert 'source_file' not in merged[FP]['scanners'][0]

    def test_template_shows_rtt_and_the_omission_note(self):
        details = format_scanner_measurements({
            'scanners': [{
                'scanner': 'moria1',
                'scanner_country': 'US',
                'bw': 20,
                'bw_mean': 20,
                'bw_median': 20,
                'obs_last': 1000,
                'measured_at': '2026-10-24T05:36:11',
                'file_created': '2026-10-24T05:36:17',
                'success': 8,
                'error_stream': 2,
            }],
        }, use_bits=False)
        env = Environment(
            loader=FileSystemLoader('allium/templates'),
            autoescape=select_autoescape(['html']),
        )
        html = env.get_template('bandwidth-file.html').render(
            relay={'bandwidth_file_details': details})
        assert 'id="bandwidth-file"' in html
        assert 'moria1' in html
        assert 'do not include a per-relay round-trip time' in html
        assert '2026-10-24 05:36:11' in html
        assert '8 ok, 2 stream errors' in html
