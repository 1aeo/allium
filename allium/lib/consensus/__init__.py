"""
Consensus evaluation module.

Operators turn this off with ``--no-consensus-evaluation``. ``allium.py`` calls
``set_consensus_evaluation_enabled`` from that flag before any worker starts.
The default is on.

This module provides per-relay consensus evaluation from CollecTor data,
including authority voting information and flag threshold analysis.
"""

# The CLI sets this before workers are counted. Library callers that never
# parse arguments keep the default, which is on.
_consensus_evaluation_enabled = True


def set_consensus_evaluation_enabled(enabled: bool) -> None:
    """Record whether this process should fetch and render consensus evaluation."""
    global _consensus_evaluation_enabled
    _consensus_evaluation_enabled = bool(enabled)


def is_consensus_evaluation_enabled() -> bool:
    """Check if consensus evaluation feature is enabled."""
    return _consensus_evaluation_enabled


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
    'set_consensus_evaluation_enabled',
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
