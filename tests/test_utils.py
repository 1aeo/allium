#!/usr/bin/env python3
"""
Test utilities module - consolidates common test setup patterns to eliminate duplication.

This module provides:
- Common mock data structures
- Reusable test setup functions
- Common patching patterns
- Utility functions for test environment setup
"""

import json
import os
import sys
import tempfile
import time
import types
from contextlib import contextmanager
from unittest.mock import Mock, MagicMock, patch

# Add the allium directory to Python path - centralized path setup
ALLIUM_ROOT = os.path.join(os.path.dirname(__file__), '..')
if ALLIUM_ROOT not in sys.path:
    sys.path.insert(0, ALLIUM_ROOT)

# Import after path setup
from allium.lib.relays import Relays


class TestDataFactory:
    """Factory class for creating common test data structures."""
    
    @staticmethod
    def create_minimal_relay_data():
        """Create minimal relay data structure for Relays constructor."""
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
    
    @staticmethod
    def create_sample_relay_data():
        """Create realistic sample relay data for testing."""
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
                    'country': 'US',
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
                    'country': 'DE',
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
    
    @staticmethod
    def create_onionoo_response(relay_count=5):
        """Create realistic onionoo API response data."""
        relays = []
        for i in range(relay_count):
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
                'country': 'US' if i % 2 == 0 else 'DE',
                'as': f'AS{12345 + i}',
                'or_addresses': [f'192.168.1.{i+1}:9001'],
                'contact': f'operator{i+1}@example.com'
            })
        
        return {
            'version': '10.0',
            'relays_published': '2024-01-01 00:00:00',
            'relays': relays
        }
    
    @staticmethod
    def create_uptime_data(relay_count=5):
        """Create realistic uptime data for testing."""
        relays = []
        for i in range(relay_count):
            relays.append({
                'fingerprint': f'AAAA{i+1:04d}BBBB{i+1:04d}CCCC{i+1:04d}DDDD{i+1:04d}EEEE{i+1:04d}',
                'uptime': {
                    '1_month': {
                        'factor': 0.01,
                        'count': 720,
                        'values': [95.0 + i, 94.0 + i, 96.0 + i, 95.5 + i, 94.5 + i]
                    },
                    '6_months': {
                        'factor': 0.01,
                        'count': 4320,
                        'values': [94.0 + i, 93.0 + i, 95.0 + i, 94.5 + i, 93.5 + i]
                    }
                }
            })
        
        return {
            'version': '10.0',
            'relays_published': '2024-01-01 00:00:00',
            'relays': relays
        }
    
    @staticmethod
    def create_aroi_leaderboard_entry(rank=1, contact_hash='test_hash'):
        """Create mock AROI leaderboard entry."""
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


class TestPatchingHelpers:
    """Helper class for common patching patterns."""
    
    @staticmethod
    @contextmanager
    def patch_relays_methods():
        """Context manager to patch all common Relays methods.
        
        Note: Methods patched here must exist in Relays class.
        Previously patched _fix_missing_observed_bandwidth was removed
        when bandwidth handling was refactored.
        """
        with patch.object(Relays, '_filter_and_fix_relays'), \
             patch.object(Relays, '_sort_by_observed_bandwidth'), \
             patch.object(Relays, '_trim_platform'), \
             patch.object(Relays, '_add_hashed_contact'), \
             patch.object(Relays, '_process_aroi_contacts'), \
             patch.object(Relays, '_preprocess_template_data'), \
             patch.object(Relays, '_categorize'), \
             patch.object(Relays, '_generate_aroi_leaderboards'), \
             patch.object(Relays, '_generate_smart_context'):
            yield
    
    @staticmethod
    def create_mock_http_response(data):
        """Create mock HTTP response object."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(data).encode('utf-8')
        return mock_response
    
    @staticmethod
    @contextmanager
    def patch_worker_environment(temp_dir):
        """Context manager to patch worker environment variables."""
        cache_dir = os.path.join(temp_dir, 'cache')
        state_file = os.path.join(temp_dir, 'state.json')
        
        with patch('allium.lib.workers.CACHE_DIR', cache_dir), \
             patch('allium.lib.workers.STATE_FILE', state_file):
            # Create directories
            os.makedirs(cache_dir, exist_ok=True)
            yield cache_dir, state_file


class TestSetupHelpers:
    """Helper class for common test setup operations."""
    
    @staticmethod
    def create_test_relays_instance(output_dir='/tmp/test', 
                                    onionoo_url='https://test.example.com',
                                    relay_data=None,
                                    use_bits=False,
                                    progress=False):
        """Create a Relays instance with common test setup."""
        if relay_data is None:
            relay_data = TestDataFactory.create_minimal_relay_data()
        
        with TestPatchingHelpers.patch_relays_methods():
            return Relays(
                output_dir=output_dir,
                onionoo_url=onionoo_url,
                relay_data=relay_data,
                use_bits=use_bits,
                progress=progress
            )
    
    @staticmethod
    def setup_jinja_environment():
        """Set up Jinja2 environment with common filters for template testing."""
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        
        template_dir = os.path.join(ALLIUM_ROOT, 'allium', 'templates')
        jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Add common filters
        try:
            from allium.lib.relays import (
                determine_unit_filter, 
                format_bandwidth_with_unit, 
                format_bandwidth_filter, 
                format_time_ago
            )
            jinja_env.filters['determine_unit'] = determine_unit_filter
            jinja_env.filters['format_bandwidth_with_unit'] = format_bandwidth_with_unit
            jinja_env.filters['format_bandwidth'] = format_bandwidth_filter
            jinja_env.filters['format_time_ago'] = format_time_ago
        except ImportError:
            pass  # Filters may not be available in all test contexts
        
        return jinja_env


class TestValidationHelpers:
    """Helper class for common test validation patterns."""
    
    @staticmethod
    def validate_json_structure(data, required_keys):
        """Validate JSON structure has required keys."""
        if not isinstance(data, dict):
            return False
        
        for key in required_keys:
            if key not in data:
                return False
        
        return True
    
    @staticmethod
    def validate_relay_data_structure(relay_data):
        """Validate relay data has proper structure."""
        required_keys = ['relays', 'sorted', 'network_totals']
        return TestValidationHelpers.validate_json_structure(relay_data, required_keys)
    
    @staticmethod
    def validate_onionoo_response(response):
        """Validate onionoo response structure."""
        required_keys = ['version', 'relays']
        return TestValidationHelpers.validate_json_structure(response, required_keys)


# Convenience functions for backward compatibility
def setup_test_environment():
    """Set up basic test environment - convenience function."""
    return TestSetupHelpers()

def create_mock_relay_data():
    """Create mock relay data - convenience function."""
    return TestDataFactory.create_minimal_relay_data()

def create_sample_relay_data():
    """Create sample relay data - convenience function."""
    return TestDataFactory.create_sample_relay_data()

def patch_relays_methods():
    """Patch Relays methods - convenience function."""
    return TestPatchingHelpers.patch_relays_methods()

def create_test_relays(output_dir='/tmp/test', relay_data=None):
    """Create test Relays instance - convenience function."""
    return TestSetupHelpers.create_test_relays_instance(
        output_dir=output_dir, 
        relay_data=relay_data
    )