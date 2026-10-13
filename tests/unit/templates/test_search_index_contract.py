"""Search-index schema contract consumed by allium-deploy's Pages Function."""

import json
import re
from typing import Any, Dict

from allium.lib.aroi_validation import get_v3_search_index_thresholds
from allium.lib.page_writer import write_pages_by_key
from allium.lib.relays import Relays
from allium.lib.search_index import PARALLEL_THRESHOLD, generate_search_index


def _generate_index(
        tmp_path, relays_data, filename, use_parallel) -> Dict[str, Any]:
    output_path = tmp_path / filename
    generate_search_index(
        relays_data,
        str(output_path),
        validated_aroi_domains={'zeta.example', 'example.org'},
        use_parallel=use_parallel,
    )
    return json.loads(output_path.read_text(encoding='utf-8'))


def _assert_search_index_contract(index) -> None:
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
    expected_v3_thresholds = {
        'explorer': 1,
        'migrating': 25,
        'mostly': 75,
        'complete': 100,
    }
    assert get_v3_search_index_thresholds() == expected_v3_thresholds
    assert lookups['v3_thresholds'] == expected_v3_thresholds

    relay = index['relays'][0]
    assert {'f', 'n', 'as', 'cc', 'ip', 'a', 'c'}.issubset(relay)


def _assert_lookup_key_order(index) -> None:
    lookups = index['lookups']
    assert list(lookups['as_names']) == sorted(lookups['as_names'])
    assert list(lookups['country_names']) == sorted(lookups['country_names'])
    assert lookups['platforms'] == sorted(lookups['platforms'])
    assert lookups['flags'] == sorted(lookups['flags'])
    assert len(lookups['validated_aroi_domains']) >= 2
    assert lookups['validated_aroi_domains'] == sorted(
        lookups['validated_aroi_domains'])


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
    parallel_filename = 'parallel-search-index.json'
    sequential_filename = 'sequential-search-index.json'

    parallel_index = _generate_index(
        tmp_path,
        search_index_parallel_contract_relays_data,
        parallel_filename,
        use_parallel=True,
    )
    sequential_index = _generate_index(
        tmp_path,
        search_index_parallel_contract_relays_data,
        sequential_filename,
        use_parallel=False,
    )

    assert parallel_index['meta']['relay_count'] > PARALLEL_THRESHOLD
    _assert_search_index_contract(parallel_index)
    _assert_lookup_key_order(parallel_index)
    assert ((tmp_path / parallel_filename).read_bytes() ==
            (tmp_path / sequential_filename).read_bytes())
    assert parallel_index['lookups'] == sequential_index['lookups']
    assert parallel_index['relays'] == sequential_index['relays']


def test_cache_manager_writes_sorted_json_keys(
        tmp_path, sorted_json_cache_payload):
    from allium.lib.file_io_utils import create_cache_manager

    cache_manager = create_cache_manager(str(tmp_path))
    assert cache_manager.save_cache('deterministic', sorted_json_cache_payload)

    rendered = (tmp_path / 'deterministic.json').read_text(encoding='utf-8')
    assert rendered == '{"a":{"b":2,"d":4},"z":1}'  # sorted keys, compact separators


def _relay_on(index, platform):
    """An Onionoo details relay reporting this platform string."""
    return {
        'fingerprint': f'{index:040X}', 'nickname': f'relay{index}', 'running': True,
        'observed_bandwidth': 1_000_000, 'consensus_weight': 100, 'flags': ['Running', 'Valid'],
        'first_seen': '2024-01-01 00:00:00', 'last_seen': '2026-10-11 12:00:00',
        'country': 'de', 'country_name': 'Germany', 'as': 'AS100', 'as_name': 'Example',
        'or_addresses': [f'192.0.2.{index}:9001'], 'platform': platform,
    }


def test_lookup_platforms_name_the_platform_pages(tmp_path):
    """Search redirects a platform to /platform/<listed name>/: each one is a written page."""
    platforms = ['Tor 0.4.8.10 on FreeBSD', 'Tor 0.4.8.10 on GNU/Linux-libre', 'Tor 0.4.8.10 on Windows 10',
                 'Tor 0.4.8.10 on Linux', 'Tor 0.4.8.10 on Linux', 'Tor 0.4.8.10 on linux',
                 'Tor 0.4.8.10 on _Linux', 'Tor 0.4.8.10']  # renamed folder; no "on", so no page
    relay_set = Relays(output_dir=str(tmp_path), onionoo_url='https://onionoo.example.invalid/details',
                       relay_data={'version': '8.0', 'relays_published': '2026-10-11 12:00:00',
                                   'relays': [_relay_on(i, p) for i, p in enumerate(platforms, 1)]},
                       mp_workers=0)
    write_pages_by_key(relay_set, 'platform')
    index = _generate_index(tmp_path, relay_set.json, 'search-index.json', use_parallel=False)

    # "linux" (one relay) would match the same searches as "Linux" (two)
    assert index['lookups']['platforms'] == ['FreeBSD', 'Linux', 'Linux-libre', 'Windows']
    for platform in index['lookups']['platforms']:
        assert (tmp_path / 'platform' / platform / 'index.html').is_file(), platform
    assert tuple(map(int, index['meta']['version'].split('.'))) >= (1, 7)


def test_lookup_platforms_list_one_name_per_case_insensitive_name(tmp_path):
    """Of platform pages that differ only by case, the one with most relays, else the first, is listed."""
    def platforms_of(relay_counts):
        pages = {key: {'relays': list(range(count))} for key, count in relay_counts.items()}
        relays_data = {'relays': [], 'sorted': {'family': {}, 'platform': pages},
                       'relays_published': '2026-10-11 12:00:00'}
        generate_search_index(relays_data, str(tmp_path / 'index.json'))
        return json.loads((tmp_path / 'index.json').read_text(encoding='utf-8'))['lookups']['platforms']

    assert platforms_of({'linux': 2, 'Linux': 1, 'FreeBSD': 1}) == ['FreeBSD', 'linux']
    assert platforms_of({'linux': 1, 'Linux': 1}) == ['Linux']
    assert platforms_of({}) == []
