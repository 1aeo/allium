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
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


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
TEST_BANDWIDTH_CACHE_HOURS = 1


# ============================================================================
# PYTEST FIXTURES - Common test data and utilities
# ============================================================================

@pytest.fixture
def temp_dir():
    """Fixture that provides a temporary directory that's cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


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
def mock_aroi_leaderboard_entry():
    """Fixture that creates a mock AROI leaderboard entry."""
    def _create_entry(rank=1, contact_hash='test_hash'):
        entry = types.SimpleNamespace()
        entry.contact_hash = contact_hash
        entry.contact_info_escaped = f'operator{rank}@example.com'
        entry.display_name = f'Operator{rank}'
        entry.rank = rank
        entry.total_relays = 10 + rank
        entry.measured_count = 5 + (rank // 2)
        entry.total_bandwidth = f'{1.0 + (rank * 0.1):.1f}'
        entry.bandwidth_unit = 'MB/s'
        entry.total_consensus_weight_pct = f'{1.0 + (rank * 0.1):.1f}%'
        entry.exit_consensus_weight_pct = f'{0.5 + (rank * 0.05):.1f}%'
        entry.guard_consensus_weight_pct = f'{0.5 + (rank * 0.05):.1f}%'
        entry.exit_count = 5 + rank
        entry.guard_count = 3 + rank
        entry.middle_count = 2 + rank
        entry.diversity_score = 50 + rank
        entry.country_count = 2 + (rank // 5)
        entry.platform_count = 1 + (rank // 3)
        entry.unique_as_count = 1 + (rank // 2)
        entry.non_linux_count = 1 + (rank // 3)
        entry.non_eu_count = 1 + (rank // 2)
        entry.non_eu_count_with_percentage = f'{1 + (rank // 2)} ({50 + rank}%)'
        entry.rare_country_count = 1 + (rank // 10)
        entry.relays_in_rare_countries = 1 + (rank // 8)
        entry.veteran_days = 100 + (rank * 10)
        entry.veteran_score = (100 + (rank * 10)) * (10 + rank)
        entry.reliability_score = f'{90.0 + rank:.1f}%'
        entry.reliability_average = f'{90.0 + rank:.1f}%'
        entry.unique_ipv4_count = 10 + rank
        entry.unique_ipv6_count = 5 + rank
        return entry
    return _create_entry


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
            _process_aroi_contacts=MagicMock(),
            _preprocess_template_data=MagicMock(),
            _categorize=MagicMock(),
            _generate_aroi_leaderboards=MagicMock(),
            _generate_smart_context=MagicMock()
        )
    return _patch


@pytest.fixture
def jinja_env():
    """Fixture that provides a configured Jinja2 environment for template testing."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    
    template_dir = project_root / 'allium' / 'templates'
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(['html', 'xml'])
    )
    
    # Add custom filters for template compatibility
    try:
        from allium.lib.relays import (
            determine_unit_filter, 
            format_bandwidth_with_unit, 
            format_bandwidth_filter, 
            format_time_ago
        )
        env.filters['determine_unit'] = determine_unit_filter
        env.filters['format_bandwidth_with_unit'] = format_bandwidth_with_unit
        env.filters['format_bandwidth'] = format_bandwidth_filter
        env.filters['format_time_ago'] = format_time_ago
    except ImportError:
        pass  # Filters may not be available in all test contexts
    
    return env


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
