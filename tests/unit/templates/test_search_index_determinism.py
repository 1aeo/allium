"""Regression test: search-index.json must be byte-deterministic.

The parallel path used to merge per-batch lookup dicts via as_completed,
so JSON key insertion order depended on thread completion order and the
file byte-differed run-to-run (breaking byte-level regression diffs of
generated site trees). Batches now merge in submission order and the
lookup maps are sorted at serialization.
"""

import json

import pytest

from allium.lib.search_index import PARALLEL_THRESHOLD, generate_search_index


def _synthetic_relays(count):
    relays = []
    for i in range(count):
        relays.append({
            'fingerprint': f'{i:040X}',
            'nickname': f'relay{i}',
            'as': f'AS{i % 400}',
            'as_name': f'Provider {i % 400} GmbH',
            'country': ['de', 'us', 'fr', 'nl', 'se'][i % 5],
            'country_name': ['Germany', 'United States', 'France',
                             'Netherlands', 'Sweden'][i % 5],
            'platform': f'Tor 0.4.{i % 3}.x on Linux',
            'flags': ['Running', 'Fast'] + (['Exit'] if i % 4 == 0 else []),
            'contact': f'op{i % 300} AT example DOT org',
        })
    return relays


@pytest.mark.parametrize('relay_count', [PARALLEL_THRESHOLD + 200])
def test_search_index_byte_deterministic_parallel(tmp_path, relay_count):
    relays_data = {
        'relays': _synthetic_relays(relay_count),
        'sorted': {'family': {}},
        'relays_published': '2026-05-05 00:00:00',
    }
    outputs = []
    for run in range(2):
        output_path = tmp_path / f'index-{run}.json'
        generate_search_index(relays_data, str(output_path), use_parallel=True)
        outputs.append(output_path.read_bytes())

    assert outputs[0] == outputs[1], (
        "search-index.json is not byte-deterministic across identical runs")

    # Sanity: semantically valid and the parallel path really ran over the
    # threshold-sized dataset
    index = json.loads(outputs[0])
    assert index['meta']['relay_count'] == relay_count
    assert list(index['lookups']['as_names']) == sorted(index['lookups']['as_names'])
    assert list(index['lookups']['country_names']) == sorted(index['lookups']['country_names'])


def test_parallel_and_sequential_lookups_agree(tmp_path):
    relays_data = {
        'relays': _synthetic_relays(PARALLEL_THRESHOLD + 200),
        'sorted': {'family': {}},
        'relays_published': '2026-05-05 00:00:00',
    }
    par_path = tmp_path / 'par.json'
    seq_path = tmp_path / 'seq.json'
    generate_search_index(relays_data, str(par_path), use_parallel=True)
    generate_search_index(relays_data, str(seq_path), use_parallel=False)
    par = json.loads(par_path.read_bytes())
    seq = json.loads(seq_path.read_bytes())
    assert par['lookups'] == seq['lookups']
    assert par['relays'] == seq['relays']
