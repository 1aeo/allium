"""
Live smoke test for the first_seen correction.

Hits the live onionoo API (details + uptime endpoints) for AS36849 (1aeo.com)
and verifies the correction either:

* repairs the chali2na relay's first_seen to be at least 6 months earlier
  than the raw value (current state -- upstream bug still present), OR
* finds nothing to correct because chali2na already has a sensible
  first_seen (upstream has been fixed -- treat as pass with info log).

Anything in between (e.g., ~50% of 1aeo relays correctable but not chali2na)
is treated as a regression.

Marked slow + system so it's excluded from the default `pytest -m "not slow"`
run. Invoke with:

    pytest -m slow tests/system/test_first_seen_correction_live.py
"""

import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

try:
    import urllib.request
    import urllib.error
except ImportError:  # pragma: no cover -- Py3
    raise

from allium.lib.first_seen_correction import correct_first_seen
from allium.lib.time_utils import parse_onionoo_timestamp


pytestmark = [pytest.mark.slow, pytest.mark.system]


CHALI2NA_FP = '0040E1791755D340BA8109F4C1849666582CF56C'
AS_QUERY = 'AS36849'
ONIONOO_DETAILS = 'https://onionoo.torproject.org/details'
ONIONOO_UPTIME = 'https://onionoo.torproject.org/uptime'


def _fetch_json(url, timeout=30):
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'allium-test/first-seen-smoke'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as e:
        pytest.skip('live onionoo unreachable: {}: {}'.format(type(e).__name__, e))


def test_chali2na_first_seen_repaired_or_already_correct():
    details = _fetch_json(
        '{}?as={}&fields=fingerprint,first_seen,nickname,running'.format(
            ONIONOO_DETAILS, AS_QUERY
        )
    )
    uptime = _fetch_json('{}?as={}'.format(ONIONOO_UPTIME, AS_QUERY))

    relays = details.get('relays') or []
    if not relays:
        pytest.skip('no relays for AS36849 in live data')

    # Locate chali2na if still present.
    chali2na = next((r for r in relays if r.get('fingerprint') == CHALI2NA_FP), None)
    if chali2na is None:
        pytest.skip('chali2na ({}) not in live 1aeo AS query'.format(CHALI2NA_FP))

    raw_first_seen = chali2na.get('first_seen')
    assert raw_first_seen, 'chali2na has no first_seen in live details data'
    raw_dt = parse_onionoo_timestamp(raw_first_seen)
    assert raw_dt is not None

    # Apply the correction.
    correct_first_seen(details, uptime)

    six_months_ago = datetime.now(tz=timezone.utc) - timedelta(days=180)

    # Re-fetch chali2na from the (mutated) details.
    chali2na_post = next(
        (r for r in details['relays'] if r.get('fingerprint') == CHALI2NA_FP), None
    )
    assert chali2na_post is not None

    corrected_first_seen = chali2na_post.get('first_seen')
    corrected_dt = parse_onionoo_timestamp(corrected_first_seen)
    assert corrected_dt is not None

    if raw_dt < six_months_ago and not chali2na_post.get('_first_seen_corrected'):
        # Upstream may have been fixed: raw first_seen is already older
        # than 6 months ago AND no correction was applied. Pass with info.
        sys.stderr.write(
            "\nchali2na: raw first_seen {} is already older than 6mo; "
            "upstream onionoo may be fixed.\n".format(raw_first_seen)
        )
        return

    # Otherwise the bug is still live and we expect a correction.
    assert chali2na_post.get('_first_seen_corrected') is True, (
        'expected first_seen correction on chali2na but none was applied. '
        'raw={}, corrected={}'.format(raw_first_seen, corrected_first_seen)
    )
    assert chali2na_post['first_seen_onionoo_raw'] == raw_first_seen
    # Corrected value must be at least 6 months earlier than raw.
    assert corrected_dt <= raw_dt - timedelta(days=180), (
        'corrected first_seen ({}) must be >=6mo earlier than raw ({})'.format(
            corrected_first_seen, raw_first_seen
        )
    )


def test_correction_rate_for_1aeo_is_high_or_zero():
    """Sanity check across the whole 1aeo operator.

    Either:
    * Upstream still buggy -> correction rate >= 80% across 1aeo.
    * Upstream fixed       -> correction rate == 0%.
    Anything in between is a regression worth investigating.
    """
    details = _fetch_json(
        '{}?as={}&fields=fingerprint,first_seen,nickname,running'.format(
            ONIONOO_DETAILS, AS_QUERY
        )
    )
    uptime = _fetch_json('{}?as={}'.format(ONIONOO_UPTIME, AS_QUERY))

    if not details.get('relays'):
        pytest.skip('no relays for AS36849 in live data')

    correct_first_seen(details, uptime)
    stats = details['_first_seen_correction_summary']
    total = stats['total']
    corrected = stats['corrected']
    ratio = corrected / total if total else 0.0

    assert ratio == 0.0 or ratio >= 0.8, (
        'unexpected correction rate {:.1%} ({}/{}); expected 0% (upstream fixed) '
        'or >=80% (bug still live); stats={}'.format(ratio, corrected, total, stats)
    )
