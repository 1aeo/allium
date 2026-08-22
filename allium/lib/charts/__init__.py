"""Build-time relay-page charts.

This package is imported by the HTML generate process. It must not import
matplotlib at module load. Rendering is a separate optional pass; see
docs/features/planned/charts/relay-page-chart-pipeline.md.
"""

from .registry import (
    RELAY_BANDWIDTH_1M_ID,
    ChartSpec,
    enabled_charts,
    get_chart,
    registered_chart_ids,
)

__all__ = [
    "RELAY_BANDWIDTH_1M_ID",
    "ChartSpec",
    "enabled_charts",
    "get_chart",
    "registered_chart_ids",
]
