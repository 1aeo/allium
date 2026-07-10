"""Search-index schema contract consumed by allium-deploy's Pages Function."""

import json
import re

from allium.lib.aroi_validation import get_v3_search_index_thresholds
from allium.lib.search_index import generate_search_index


def test_generated_search_index_contract(tmp_path):
    relays_data = {
        'relays': [
            {
                'fingerprint': 'A' * 40,
                'nickname': 'contractRelay',
                'aroi_domain': 'example.org',
                'contact_md5': '0123456789abcdef0123456789abcdef',
                'as': 'AS64500',
                'as_name': 'Example Network',
                'country': 'DE',
                'country_name': 'Germany',
                'or_addresses': ['203.0.113.7:9001'],
                'platform': 'Tor 0.4.8.x on Linux',
                'flags': ['Running', 'Fast', 'Guard'],
            }
        ],
        'sorted': {'family': {}},
        'relays_published': '2026-05-05 00:00:00',
    }

    output_path = tmp_path / 'search-index.json'
    generate_search_index(
        relays_data,
        str(output_path),
        validated_aroi_domains={'example.org'},
        use_parallel=False,
    )
    index = json.loads(output_path.read_text(encoding='utf-8'))

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


def test_cache_manager_writes_sorted_json_keys(tmp_path):
    from allium.lib.file_io_utils import create_cache_manager

    cache_manager = create_cache_manager(str(tmp_path))
    assert cache_manager.save_cache('deterministic', {
        'z': 1,
        'a': {'d': 4, 'b': 2},
    })

    rendered = (tmp_path / 'deterministic.json').read_text(encoding='utf-8')
    assert rendered.index('"a"') < rendered.index('"z"')
    assert rendered.index('"b"') < rendered.index('"d"')
