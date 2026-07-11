"""Search-index schema contract consumed by allium-deploy's Pages Function."""

import json
import re

from allium.lib.aroi_validation import get_v3_search_index_thresholds
from allium.lib.search_index import PARALLEL_THRESHOLD, generate_search_index


def _generate_index(tmp_path, relays_data, filename, use_parallel):
    output_path = tmp_path / filename
    generate_search_index(
        relays_data,
        str(output_path),
        validated_aroi_domains={'example.org'},
        use_parallel=use_parallel,
    )
    return json.loads(output_path.read_text(encoding='utf-8'))


def _assert_search_index_contract(index):
    assert {'meta', 'relays', 'families', 'lookups'}.issubset(index)
    assert isinstance(index['meta'].get('version'), str)
    assert re.fullmatch(r'\d+\.\d+', index['meta']['version'])

    lookups = index['lookups']
    assert {
        'as_names',
        'country_names',
        'platforms',
        'flags',
        'validated_aroi_domains',
    }.issubset(lookups)
    assert lookups['v3_thresholds'] == get_v3_search_index_thresholds()

    relay = index['relays'][0]
    assert {'f', 'n', 'as', 'cc', 'ip', 'a', 'c'}.issubset(relay)


def _assert_lookup_key_order(index):
    lookups = index['lookups']
    assert list(lookups['as_names']) == sorted(lookups['as_names'])
    assert list(lookups['country_names']) == sorted(lookups['country_names'])
    assert lookups['platforms'] == sorted(lookups['platforms'])
    assert lookups['flags'] == sorted(lookups['flags'])


def test_generated_search_index_contract(
        tmp_path, search_index_contract_relays_data):
    index = _generate_index(
        tmp_path,
        search_index_contract_relays_data,
        'search-index.json',
        use_parallel=False,
    )

    _assert_search_index_contract(index)
    _assert_lookup_key_order(index)


def test_generated_search_index_contract_parallel(
        tmp_path, search_index_parallel_contract_relays_data):
    parallel_index = _generate_index(
        tmp_path,
        search_index_parallel_contract_relays_data,
        'parallel-search-index.json',
        use_parallel=True,
    )
    sequential_index = _generate_index(
        tmp_path,
        search_index_parallel_contract_relays_data,
        'sequential-search-index.json',
        use_parallel=False,
    )

    assert parallel_index['meta']['relay_count'] > PARALLEL_THRESHOLD
    _assert_search_index_contract(parallel_index)
    _assert_lookup_key_order(parallel_index)
    assert parallel_index['lookups'] == sequential_index['lookups']
    assert parallel_index['relays'] == sequential_index['relays']


def test_cache_manager_writes_sorted_json_keys(
        tmp_path, sorted_json_cache_payload):
    from allium.lib.file_io_utils import create_cache_manager

    cache_manager = create_cache_manager(str(tmp_path))
    assert cache_manager.save_cache('deterministic', sorted_json_cache_payload)

    rendered = (tmp_path / 'deterministic.json').read_text(encoding='utf-8')
    assert rendered.index('"a"') < rendered.index('"z"')
    assert rendered.index('"b"') < rendered.index('"d"')
