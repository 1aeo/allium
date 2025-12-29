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

# Export flag threshold constants and helpers for easy auditing
from .flag_thresholds import (
    # Constants
    SECONDS_PER_DAY,
    GUARD_BW_GUARANTEE,
    GUARD_TK_DEFAULT,
    GUARD_WFU_DEFAULT,
    HSDIR_TK_DEFAULT,
    HSDIR_WFU_DEFAULT,
    FAST_BW_GUARANTEE,
    FLAG_ORDER,
    # Helper functions
    check_guard_eligibility,
    check_hsdir_eligibility,
    check_fast_eligibility,
    check_stable_eligibility,
    get_flag_thresholds_summary,
    sort_flags,
)

__all__ = [
    # Main classes
    'CollectorFetcher',
    'AuthorityMonitor', 
    'format_relay_diagnostics',
    'format_authority_diagnostics',
    'is_enabled',
    'COLLECTOR_DIAGNOSTICS_ENABLED',
    # Flag threshold constants
    'SECONDS_PER_DAY',
    'GUARD_BW_GUARANTEE',
    'GUARD_TK_DEFAULT',
    'GUARD_WFU_DEFAULT',
    'HSDIR_TK_DEFAULT',
    'HSDIR_WFU_DEFAULT',
    'FAST_BW_GUARANTEE',
    'FLAG_ORDER',
    # Flag eligibility helpers
    'check_guard_eligibility',
    'check_hsdir_eligibility',
    'check_fast_eligibility',
    'check_stable_eligibility',
    'get_flag_thresholds_summary',
    'sort_flags',
]
