"""
Consensus troubleshooting module.
Feature flag: ALLIUM_COLLECTOR_DIAGNOSTICS (default: true)

This module provides per-relay diagnostics from CollecTor data,
including authority voting information and flag threshold analysis.
"""

import os

# Feature flag for gradual rollout
COLLECTOR_DIAGNOSTICS_ENABLED = os.environ.get(
    'ALLIUM_COLLECTOR_DIAGNOSTICS', 'true'
).lower() == 'true'


def is_enabled() -> bool:
    """Check if collector diagnostics feature is enabled."""
    return COLLECTOR_DIAGNOSTICS_ENABLED


# Export main classes
from .collector_fetcher import CollectorFetcher
from .authority_monitor import AuthorityMonitor
from .diagnostics import format_relay_diagnostics, format_authority_diagnostics

__all__ = [
    'CollectorFetcher',
    'AuthorityMonitor', 
    'format_relay_diagnostics',
    'format_authority_diagnostics',
    'is_enabled',
    'COLLECTOR_DIAGNOSTICS_ENABLED',
]
