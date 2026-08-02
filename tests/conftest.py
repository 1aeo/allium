"""
Pytest configuration file.

This file is automatically loaded by pytest and configures:
- Python path to include the project root
- Pre-loads allium package to avoid import conflicts
- Common fixtures for tests
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from tests.unit.prometheus_fixtures import (
    make_relay as _make_relay,
    make_relay_set as _make_relay_set,
    sample_aroi_data as _sample_aroi_data,
    sample_dns_metadata as _sample_dns_metadata,
)

# ============================================================================
# PATH SETUP
# ============================================================================

# Get the absolute path to the project root
project_root = Path(__file__).parent.parent.absolute()
project_root_str = str(project_root)

# Ensure project root is at the start of sys.path
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)
elif sys.path.index(project_root_str) != 0:
    sys.path.remove(project_root_str)
    sys.path.insert(0, project_root_str)

# Also add tests directory to path for test_utils imports
tests_dir = str(Path(__file__).parent.absolute())
if tests_dir not in sys.path:
    sys.path.insert(0, tests_dir)

# Critical: Pre-load allium as a PACKAGE before any test imports
# This prevents Python from treating allium/allium.py as the 'allium' module
# instead of allium/__init__.py as the 'allium' package
if 'allium' not in sys.modules:
    allium_init = project_root / 'allium' / '__init__.py'
    spec = importlib.util.spec_from_file_location('allium', str(allium_init),
                                                   submodule_search_locations=[str(project_root / 'allium')])
    allium_module = importlib.util.module_from_spec(spec)
    sys.modules['allium'] = allium_module
    spec.loader.exec_module(allium_module)

# Also set PYTHONPATH for subprocess calls
os.environ['PYTHONPATH'] = project_root_str + os.pathsep + os.environ.get('PYTHONPATH', '')


# ============================================================================
# COMMON TEST CONSTANTS
# ============================================================================

# URL constants used across multiple test files
TEST_DETAILS_URL = "https://test.onionoo.torproject.org/details"
TEST_UPTIME_URL = "https://test.onionoo.torproject.org/uptime"
TEST_BANDWIDTH_URL = "https://test.onionoo.torproject.org/bandwidth"
TEST_AROI_URL = "https://test.aroi.url/validate"
TEST_EXIT_DNS_HEALTH_URL = "https://test.exitdnshealth.url/latest.json"
TEST_BANDWIDTH_CACHE_HOURS = 1

# The 8 currently-voting directory authorities (gabelmoo removed) - alphabetical.
# Shared by the dynamic voting-authority tests (collector fetcher, diagnostics).
ACTIVE_VOTING_AUTHORITIES_8 = ['bastet', 'dannenberg', 'dizum', 'faravahar',
                               'longclaw', 'maatuska', 'moria1', 'tor26']


# ============================================================================
# PYTEST FIXTURES - Common test data and utilities
# ============================================================================

@pytest.fixture
def temp_dir():
    """Fixture that provides a temporary directory that's cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def isolated_worker_registry(monkeypatch):
    """Give a test a fresh worker-status registry."""
    from allium.lib import workers

    registry = {}
    monkeypatch.setattr(workers, '_worker_status', registry)
    return registry


@pytest.fixture
def consensus_evaluation_enabled(monkeypatch):
    """Enable consensus workers independently of the process environment."""
    from allium.lib import consensus

    monkeypatch.setattr(consensus, 'is_consensus_evaluation_enabled', lambda: True)


@pytest.fixture
def successful_worker_backends(monkeypatch):
    """Replace worker network boundaries with deterministic successful data."""
    from allium.lib import consensus, workers

    uptime_data = json.dumps({'relays': []}).encode('utf-8')
    monkeypatch.setattr(
        workers,
        '_fetch_url_with_total_timeout',
        lambda *_args, **_kwargs: uptime_data,
    )

    collector = MagicMock()
    collector.fetch_all.return_value = {
        'votes': {'moria1': {}},
        'relay_index': {'TEST': {}},
        'fetched_at': '2026-01-01T00:00:00+00:00',
        'consensus_method_info': {'total_voters': 1},
    }
    collector_factory = MagicMock(return_value=collector)
    monkeypatch.setattr(consensus, 'CollectorFetcher', collector_factory)

    monitor = MagicMock()
    monitor.check_all_authorities.return_value = {
        'moria1': {'online': True, 'latency_ms': 1},
    }
    monitor.get_summary.return_value = {
        'online_count': 1,
        'total_authorities': 1,
        'checked_at': '2026-01-01T00:00:00+00:00',
    }
    monitor.get_alerts.return_value = []
    monitor_factory = MagicMock(return_value=monitor)
    monkeypatch.setattr(consensus, 'AuthorityMonitor', monitor_factory)

    return {
        'collector': collector_factory,
        'consensus_health': monitor_factory,
    }


@pytest.fixture
def voting_registry_8_voters():
    """Set the shared authority registry to the 8 active voters (gabelmoo removed).

    Updates the module singleton via the global update_voting_authorities()
    wrapper before the test and restores the hardcoded fallback afterwards, so
    dynamic-voting tests never leak state into other tests.
    """
    from allium.lib.consensus.collector_fetcher import (
        get_authority_registry,
        update_voting_authorities,
    )
    registry = get_authority_registry()
    update_voting_authorities(ACTIVE_VOTING_AUTHORITIES_8)
    yield registry
    registry.clear_voting_authorities()


@pytest.fixture
def make_relays(temp_dir):
    """Factory that builds a Relays instance writing into a per-test temp directory.

    Shared setup for the directory-authority integration tests (and any other
    test that needs a real Relays object without hitting the network).
    """
    from allium.lib.relays import Relays

    def _make(relay_data, onionoo_url=TEST_DETAILS_URL) -> Relays:
        return Relays(temp_dir, onionoo_url, relay_data)

    return _make


@pytest.fixture
def mock_uptime_response():
    """Onionoo uptime document for three mock directory authorities
    (moria1: good, tor26: excellent, dannenberg: poor uptime)."""
    return {
        "version": "10.0",
        "build_revision": "unknown",
        "relays_published": "2025-01-01 00:00:00",
        "relays": [
            {
                "fingerprint": "9695DFC35FFEB861329B9F1AB04C46397020CE31",
                "uptime": {
                    "1_month": {
                        "factor": 0.01,
                        "count": 720,
                        "values": [99.2, 98.8, 99.1, 99.0, 98.9]  # Good uptime
                    },
                    "6_months": {
                        "factor": 0.01,
                        "count": 4320,
                        "values": [98.5, 98.8, 99.0, 98.7, 98.6]
                    },
                    "1_year": {
                        "factor": 0.01,
                        "count": 8760,
                        "values": [97.5, 97.8, 98.0, 97.9, 97.6]
                    },
                    "5_years": {
                        "factor": 0.01,
                        "count": 43800,
                        "values": [96.8, 97.0, 97.2, 96.9, 96.7]
                    }
                }
            },
            {
                "fingerprint": "847B1F850344D7876491A54892F904934E4EB85D",
                "uptime": {
                    "1_month": {
                        "factor": 0.01,
                        "count": 720,
                        "values": [99.8, 99.6, 99.7, 99.5, 99.9]  # Excellent uptime
                    },
                    "6_months": {
                        "factor": 0.01,
                        "count": 4320,
                        "values": [99.6, 99.4, 99.5, 99.3, 99.7]
                    },
                    "1_year": {
                        "factor": 0.01,
                        "count": 8760,
                        "values": [99.1, 99.0, 99.2, 98.9, 99.3]
                    },
                    "5_years": {
                        "factor": 0.01,
                        "count": 43800,
                        "values": [98.7, 98.5, 98.9, 98.6, 98.8]
                    }
                }
            },
            {
                "fingerprint": "7BE683E65D48141321C5ED92F075C55364AC7123",
                "uptime": {
                    "1_month": {
                        "factor": 0.01,
                        "count": 720,
                        "values": [89.2, 88.5, 90.1, 87.8, 89.9]  # Poor uptime
                    },
                    "6_months": {
                        "factor": 0.01,
                        "count": 4320,
                        "values": [85.7, 86.2, 85.0, 86.8, 85.3]
                    },
                    "1_year": {
                        "factor": 0.01,
                        "count": 8760,
                        "values": [82.1, 83.0, 81.5, 82.8, 81.9]
                    },
                    "5_years": {
                        "factor": 0.01,
                        "count": 43800,
                        "values": [78.5, 79.2, 78.0, 79.8, 78.1]
                    }
                }
            }
        ]
    }


@pytest.fixture
def make_relay():
    return _make_relay


@pytest.fixture
def make_relay_set():
    return _make_relay_set


@pytest.fixture
def sample_aroi_data():
    return _sample_aroi_data


@pytest.fixture
def sample_aroi_metadata():
    return _sample_aroi_data


@pytest.fixture
def sample_dns_metadata():
    return _sample_dns_metadata


@pytest.fixture
def minimal_relay_data():
    """Fixture that provides minimal relay data structure for Relays constructor."""
    return {
        'relays': [],
        'sorted': {},
        'network_totals': {
            'total_relays': 0,
            'guard_count': 0,
            'middle_count': 0,
            'exit_count': 0,
            'measured_relays': 0,
            'measured_percentage': 0.0,
            'guard_consensus_weight': 0,
            'middle_consensus_weight': 0,
            'exit_consensus_weight': 0,
            'total_network_bandwidth': 0,
            'total_guard_bandwidth': 0,
            'total_exit_bandwidth': 0,
            'total_consensus_weight': 0
        }
    }


@pytest.fixture
def sample_relay_data():
    """Fixture that provides realistic sample relay data for testing."""
    return {
        'relays': [
            {
                'fingerprint': 'AAAA1111BBBB2222CCCC3333DDDD4444EEEE5555',
                'nickname': 'TestRelay1',
                'contact': 'operator1@example.com',
                'or_addresses': ['192.168.1.1:9001', '[2001:db8::1]:9001'],
                'observed_bandwidth': 1000000,
                'consensus_weight': 100,
                'advertised_bandwidth': 1200000,
                'flags': ['Fast', 'Stable', 'Running', 'V2Dir'],
                'running': True,
                'country': 'us',
                'country_name': 'United States',
                'as': '12345',
                'as_name': 'Test AS',
                'first_seen': '2023-01-01 00:00:00',
                'last_seen': '2024-01-01 00:00:00',
                'last_restarted': '2024-01-01 00:00:00',
                'platform': 'Tor 0.4.8.10 on Linux',
                'version': '0.4.8.10',
                'version_status': 'recommended',
                'exit_policy': ['accept *:80', 'accept *:443', 'reject *:*'],
                'uptime': 85.5
            },
            {
                'fingerprint': 'BBBB2222CCCC3333DDDD4444EEEE5555FFFF6666',
                'nickname': 'TestRelay2',
                'contact': 'operator2@example.com',
                'or_addresses': ['192.168.1.2:9001'],
                'observed_bandwidth': 2000000,
                'consensus_weight': 200,
                'advertised_bandwidth': 2400000,
                'flags': ['Fast', 'Guard', 'Running', 'V2Dir'],
                'running': True,
                'country': 'de',
                'country_name': 'Germany',
                'as': '67890',
                'as_name': 'Test AS 2',
                'first_seen': '2022-01-01 00:00:00',
                'last_seen': '2024-01-01 00:00:00',
                'last_restarted': '2024-01-01 00:00:00',
                'platform': 'Tor 0.4.8.10 on Linux',
                'version': '0.4.8.10',
                'version_status': 'recommended',
                'exit_policy': ['reject *:*'],
                'uptime': 92.3
            }
        ]
    }


@pytest.fixture
def search_index_contract_relays_data():
    """Small relay set for the search-index public contract tests."""
    return {
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


@pytest.fixture
def search_index_parallel_contract_relays_data():
    """Relay set large enough to force search-index threaded processing."""
    from allium.lib.search_index import PARALLEL_THRESHOLD

    countries = [('de', 'Germany'), ('us', 'United States'),
                 ('fr', 'France'), ('nl', 'Netherlands'), ('se', 'Sweden')]
    relays = []
    for i in range(PARALLEL_THRESHOLD + 200):
        country, country_name = countries[i % len(countries)]
        relays.append({
            'fingerprint': f'{i:040X}',
            'nickname': f'contractRelay{i}',
            'aroi_domain': 'example.org' if i % 17 == 0 else '',
            'contact_md5': f'{i % 65536:032x}',
            'as': f'AS{i % 400}',
            'as_name': f'Provider {i % 400}',
            'country': country,
            'country_name': country_name,
            'or_addresses': [f'203.0.113.{i % 255}:9001'],
            'platform': f'Tor 0.4.{i % 3}.x on Linux',
            'flags': ['Running', 'Fast'] + (['Exit'] if i % 4 == 0 else []),
        })

    return {
        'relays': relays,
        'sorted': {'family': {}},
        'relays_published': '2026-05-05 00:00:00',
    }


@pytest.fixture
def sorted_json_cache_payload():
    """Nested payload for verifying deterministic JSON cache rendering."""
    return {
        'z': 1,
        'a': {'d': 4, 'b': 2},
    }


@pytest.fixture
def onionoo_response():
    """Fixture that provides realistic onionoo API response data with 5 relays."""
    relays = []
    for i in range(5):
        relays.append({
            'nickname': f'TestRelay{i+1}',
            'fingerprint': f'AAAA{i+1:04d}BBBB{i+1:04d}CCCC{i+1:04d}DDDD{i+1:04d}EEEE{i+1:04d}',
            'running': True,
            'observed_bandwidth': 1000000 + (i * 100000),
            'consensus_weight': 100 + (i * 10),
            'flags': ['Running', 'Valid'] + (['Fast'] if i % 2 == 0 else []),
            'first_seen': '2023-01-01 00:00:00',
            'last_seen': '2024-01-01 00:00:00',
            'platform': f'Tor 0.4.8.{10+i} on Linux',
            'country': 'us' if i % 2 == 0 else 'de',
            'as': f'AS{12345 + i}',
            'or_addresses': [f'192.168.1.{i+1}:9001'],
            'contact': f'operator{i+1}@example.com'
        })
    
    return {
        'version': '10.0',
        'relays_published': '2024-01-01 00:00:00',
        'relays': relays
    }


@pytest.fixture
def uptime_data():
    """Fixture that provides realistic uptime data for 5 relays."""
    relays = []
    for i in range(5):
        relays.append({
            'fingerprint': f'AAAA{i+1:04d}BBBB{i+1:04d}CCCC{i+1:04d}DDDD{i+1:04d}EEEE{i+1:04d}',
            'uptime': {
                '1_month': {
                    'factor': 0.01,
                    'count': 720,
                    'values': [950 + i for _ in range(35)]  # 35 values for sufficient data
                },
                '6_months': {
                    'factor': 0.01,
                    'count': 4320,
                    'values': [940 + i for _ in range(35)]
                }
            }
        })
    
    return {
        'version': '10.0',
        'relays_published': '2024-01-01 00:00:00',
        'relays': relays
    }


@pytest.fixture
def stub_bandwidth_formatter():
    """Lightweight bandwidth formatter stub for AROI leaderboard unit tests."""
    from helpers.fixtures import StubBandwidthFormatter
    return StubBandwidthFormatter()


@pytest.fixture
def mock_aroi_leaderboard_entry():
    """Fixture that creates a mock AROI leaderboard entry.

    Delegates to the shared TestDataFactory so the mock entry schema lives
    in exactly one place and cannot drift between test suites."""
    from helpers.fixtures import TestDataFactory
    return TestDataFactory.create_aroi_leaderboard_entry


@pytest.fixture
def jinja_env():
    """Jinja2 environment loading allium templates with the custom filters
    they depend on (shared helper in helpers.fixtures)."""
    from helpers.fixtures import TestSetupHelpers
    return TestSetupHelpers.setup_jinja_environment()


@pytest.fixture
def mock_aroi_leaderboards(mock_aroi_leaderboard_entry):
    """25 shared-schema mock entries (3 pagination pages) for every AROI
    category rendered through the paginated generic ranking tables."""
    from helpers.fixtures import AROI_PAGINATED_CATEGORIES
    return {
        category: [
            mock_aroi_leaderboard_entry(rank=i + 1, contact_hash=f'hash{i + 1}')
            for i in range(25)
        ]
        for category in AROI_PAGINATED_CATEGORIES
    }


@pytest.fixture
def aroi_template_context(mock_aroi_leaderboards):
    """Template context for rendering aroi-leaderboards.html with mock data."""
    from helpers.fixtures import AROI_CATEGORY_TITLES, AROI_PAGINATED_CATEGORIES
    return {
        'relays': {
            'json': {
                'aroi_leaderboards': {
                    'leaderboards': mock_aroi_leaderboards,
                    'summary': {
                        'categories': dict(AROI_CATEGORY_TITLES),
                        'total_operators': 150,
                        'total_bandwidth_formatted': '1.5 GB/s',
                        'total_consensus_weight_pct': '25.5%',
                        'live_categories_count': len(AROI_PAGINATED_CATEGORIES),
                        'update_timestamp': '2025-06-15 01:00:00 UTC'
                    }
                }
            },
            'use_bits': False
        },
        'page_ctx': {
            'path_prefix': './'
        }
    }


@pytest.fixture
def rendered_aroi_leaderboards(jinja_env, aroi_template_context):
    """aroi-leaderboards.html rendered with the mock AROI template context."""
    template = jinja_env.get_template('aroi-leaderboards.html')
    return template.render(**aroi_template_context)


@pytest.fixture
def mock_http_response():
    """Fixture that creates a mock HTTP response object."""
    def _create_response(data):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(data).encode('utf-8')
        return mock_response
    return _create_response


@pytest.fixture
def patch_relays_methods():
    """Fixture that provides a context manager to patch all common Relays methods."""
    from allium.lib.relays import Relays
    
    def _patch():
        return patch.multiple(
            Relays,
            _filter_and_fix_relays=MagicMock(),
            _sort_by_observed_bandwidth=MagicMock(),
            _trim_platform=MagicMock(),
            _add_hashed_contact=MagicMock(),
            _preprocess_template_data=MagicMock(),
            _categorize=MagicMock(),
            _generate_aroi_leaderboards=MagicMock(),
            _generate_smart_context=MagicMock()
        )
    return _patch


@pytest.fixture
def templates_dir():
    """Fixture that provides the allium templates directory as a Path."""
    return project_root / 'allium' / 'templates'


@pytest.fixture
def jinja_env(templates_dir):
    """Fixture that provides a configured Jinja2 environment for template testing."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(['html', 'xml'])
    )
    
    # Add custom filters for template compatibility.
    # NOTE: these moved out of allium.lib.relays in the simplification refactor;
    # import from their canonical homes so the filters are actually registered.
    from allium.lib.bandwidth_formatter import (
        determine_unit_filter,
        format_bandwidth_with_unit,
        format_bandwidth_filter,
    )
    from allium.lib.time_utils import format_time_ago
    env.filters['determine_unit'] = determine_unit_filter
    env.filters['format_bandwidth_with_unit'] = format_bandwidth_with_unit
    env.filters['format_bandwidth'] = format_bandwidth_filter
    env.filters['format_time_ago'] = format_time_ago
    
    return env


@pytest.fixture
def process_relays(tmp_path):
    """Factory fixture: run the full (unpatched) Relays init pipeline on raw
    onionoo-shaped relay dicts and return the Relays instance.

    Use this when a test must exercise real preprocessing
    (_preprocess_template_data et al.). Unlike
    TestSetupHelpers.create_test_relays_instance, nothing is mocked out.
    """
    def _process(relays):
        from allium.lib.relays import Relays
        return Relays(
            output_dir=str(tmp_path),
            onionoo_url='https://test.example.com',
            relay_data={'relays': relays},
            use_bits=False,
            progress=False,
        )
    return _process


@pytest.fixture(scope='module')
def overload_relay_set(tmp_path_factory):
    """Module-scoped Relays instance with 4 relays (2 flagged overloaded).

    Shared fixture for group-overload summary tests. Module-scoped because the
    full Relays init pipeline (categorize -> leaderboards -> intelligence) is
    expensive; one instance serves all wiring tests. stability_is_overloaded is
    applied post-init since it is normally set during bandwidth enrichment.
    """
    from allium.lib.relays import Relays

    n = 4
    relays = [{
        'nickname': f'Relay{i}', 'fingerprint': f'{i:040d}', 'running': True,
        'flags': ['Running', 'Valid'], 'observed_bandwidth': 1_000_000,
        'consensus_weight': 100, 'consensus_weight_fraction': 0.01,
        'or_addresses': [f'192.0.2.{i + 1}:9001'],
        'as': 'AS64500', 'as_name': 'Test AS',
        'country': 'us', 'country_name': 'United States', 'platform': 'Linux',
        'first_seen': '2023-01-01 00:00:00', 'last_seen': '2026-07-12 00:00:00',
        'contact': 'ops@example.com', 'measured': True,
        'effective_family': [f'{j:040d}' for j in range(n)],
    } for i in range(n)]

    rs = Relays(output_dir=str(tmp_path_factory.mktemp('overload')),
                onionoo_url=TEST_DETAILS_URL,
                relay_data={'relays': relays},
                use_bits=False, progress=False, mp_workers=0)
    for i, relay in enumerate(rs.json['relays']):
        relay['stability_is_overloaded'] = i < 2  # 2 of 4 overloaded
    return rs


# ============================================================================
# PYTEST HOOKS
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
