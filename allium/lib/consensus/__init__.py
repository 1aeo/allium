"""
Consensus evaluation module.
Feature flag: ALLIUM_CONSENSUS_EVALUATION (default: true)

This module provides per-relay consensus evaluation from CollecTor data,
including authority voting information and flag threshold analysis.
"""

import os

# Feature flag for gradual rollout
CONSENSUS_EVALUATION_ENABLED = os.environ.get(
    'ALLIUM_CONSENSUS_EVALUATION', 'true'
).lower() == 'true'


def is_consensus_evaluation_enabled() -> bool:
    """Check if consensus evaluation feature is enabled."""
    return CONSENSUS_EVALUATION_ENABLED


# Export main classes
from .collector_fetcher import CollectorFetcher
from .authority_monitor import AuthorityMonitor
from .consensus_evaluation import format_relay_consensus_evaluation, format_authority_consensus_evaluation

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
    'format_relay_consensus_evaluation',
    'format_authority_consensus_evaluation',
    'is_consensus_evaluation_enabled',
    'CONSENSUS_EVALUATION_ENABLED',
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
