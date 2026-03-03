"""
File: api_diagnostics.py

Collects diagnostics information about all API data sources powering the site.
Used by the API Diagnostics page to show freshness, health, and dependency info.

Each API source is classified by freshness:
  - fresh:  cache age < 50% of max age
  - aging:  cache age 50-100% of max age
  - stale:  cache age > max age OR worker status is "stale"
  - unavailable: API disabled or no data
"""

import time
from datetime import datetime

from .workers import (
    get_all_worker_status,
    _cache_manager,
    DETAILS_CACHE_MAX_AGE_HOURS,
    UPTIME_CACHE_MAX_AGE_HOURS,
    BANDWIDTH_CACHE_MAX_AGE_HOURS,
    AROI_CACHE_MAX_AGE_HOURS,
    COLLECTOR_CACHE_MAX_AGE_HOURS,
    DESCRIPTORS_CACHE_MAX_AGE_HOURS,
)


# ============================================================================
# API METADATA REGISTRY
# ============================================================================
# Defines display information, ownership, and site section dependencies
# for each API source. To add a new API: add one entry here.
# ============================================================================

API_METADATA = {
    "onionoo_details": {
        "display_name": "Onionoo Details API",
        "owner": "Tor Project",
        "url_arg": "onionoo_details_url",
        "default_url": "https://onionoo.torproject.org/details",
        "expected_frequency": "~30 minutes",
        "cache_max_age_hours": DETAILS_CACHE_MAX_AGE_HOURS,
        "count_field": "relays",
        "count_label": "relays",
        "affected_sections": [
            "All Relay Pages",
            "Top 500 Relays",
            "Browse by Network / Country / Platform",
            "Individual Relay Info Pages",
            "Network Health Dashboard",
        ],
    },
    "onionoo_uptime": {
        "display_name": "Onionoo Uptime API",
        "owner": "Tor Project",
        "url_arg": "onionoo_uptime_url",
        "default_url": "https://onionoo.torproject.org/uptime",
        "expected_frequency": "~30 minutes",
        "cache_max_age_hours": UPTIME_CACHE_MAX_AGE_HOURS,
        "count_field": "relays",
        "count_label": "relays",
        "affected_sections": [
            "Relay Uptime Percentages",
            "AROI Leaderboards (uptime rankings)",
            "Contact Page Reliability",
            "Network Health Uptime Stats",
        ],
    },
    "onionoo_bandwidth": {
        "display_name": "Onionoo Bandwidth API",
        "owner": "Tor Project",
        "url_arg": "onionoo_bandwidth_url",
        "default_url": "https://onionoo.torproject.org/bandwidth",
        "expected_frequency": "~12 hours (historical data)",
        "cache_max_age_hours": BANDWIDTH_CACHE_MAX_AGE_HOURS,
        "count_field": "relays",
        "count_label": "relays",
        "affected_sections": [
            "Historical Bandwidth on Relay Pages",
            "Total Data Transferred",
            "AROI Bandwidth Rankings",
            "Network Health Bandwidth Stats",
        ],
    },
    "aroi_validation": {
        "display_name": "AROI Validation API",
        "owner": "1st Amendment Encrypted Openness (1AEO)",
        "url_arg": "aroi_url",
        "default_url": "https://aroivalidator.1aeo.com/latest.json",
        "expected_frequency": "~1 hour",
        "cache_max_age_hours": AROI_CACHE_MAX_AGE_HOURS,
        "count_field": "results",
        "count_label": "results",
        "affected_sections": [
            "AROI Validation Badges",
            "Contact Page Validation Status",
        ],
    },
    "collector_consensus": {
        "display_name": "CollecTor Consensus API",
        "owner": "Tor Project",
        "url_arg": None,
        "default_url": "https://collector.torproject.org",
        "url_note": "authority votes",
        "expected_frequency": "~1 hour (consensus cycle)",
        "cache_max_age_hours": COLLECTOR_CACHE_MAX_AGE_HOURS,
        "count_field": "relay_index",
        "count_label": "relays indexed",
        "affected_sections": [
            "Consensus Evaluation on Relay Pages",
            "Directory Authorities Page",
            "Network Health Consensus Data",
        ],
    },
    "collector_descriptors": {
        "display_name": "CollecTor Descriptors API",
        "owner": "Tor Project",
        "url_arg": None,
        "default_url": "https://collector.torproject.org/recent/relay-descriptors/server-descriptors/",
        "url_note": "server descriptors",
        "expected_frequency": "~1 hour (hourly incremental files)",
        "cache_max_age_hours": DESCRIPTORS_CACHE_MAX_AGE_HOURS,
        "count_field": "all_seen_fingerprints",
        "count_label": "relays tracked",
        "affected_sections": [
            "Happy Families / Family-Cert Classification",
            "Family Pages",
            "Contact Pages (family support type)",
        ],
    },
}

# ============================================================================
# SITE SECTION DEPENDENCY MAP
# ============================================================================
# Maps site sections to the APIs they depend on, plus a link path.
# Used by the dependency table on the diagnostics page.
# ============================================================================

SECTION_DEPENDENCIES = [
    {
        "section": "All Relay Pages",
        "apis": ["onionoo_details"],
        "link": "misc/all.html",
    },
    {
        "section": "Top 500 Relays",
        "apis": ["onionoo_details"],
        "link": "top500.html",
    },
    {
        "section": "Relay Uptime and Stability",
        "apis": ["onionoo_details", "onionoo_uptime"],
        "link": "",
        "link_label": "(per-relay pages)",
    },
    {
        "section": "AROI Operator Leaderboards",
        "apis": ["onionoo_details", "onionoo_uptime", "onionoo_bandwidth"],
        "link": "index.html",
    },
    {
        "section": "AROI Validation Badges",
        "apis": ["aroi_validation"],
        "link": "",
        "link_label": "(contact pages)",
    },
    {
        "section": "Network Health Dashboard",
        "apis": [
            "onionoo_details", "onionoo_uptime", "onionoo_bandwidth",
            "aroi_validation", "collector_consensus", "collector_descriptors",
        ],
        "link": "network-health.html",
    },
    {
        "section": "Directory Authorities",
        "apis": ["onionoo_details", "collector_consensus"],
        "link": "misc/authorities.html",
    },
    {
        "section": "Family Pages",
        "apis": ["onionoo_details", "collector_descriptors"],
        "link": "",
        "link_label": "(family detail pages)",
    },
    {
        "section": "Contact / Operator Pages",
        "apis": [
            "onionoo_details", "onionoo_uptime", "onionoo_bandwidth",
            "aroi_validation", "collector_descriptors",
        ],
        "link": "",
        "link_label": "(contact detail pages)",
    },
    {
        "section": "Consensus Evaluation",
        "apis": ["onionoo_details", "collector_consensus"],
        "link": "",
        "link_label": "(per-relay pages)",
    },
    {
        "section": "Browse by Network / Country / Platform",
        "apis": ["onionoo_details"],
        "link": "",
        "link_label": "(misc sorted pages)",
    },
]


# ============================================================================
# FRESHNESS CLASSIFICATION
# ============================================================================

def _classify_freshness(cache_age_seconds, cache_max_age_hours, worker_status):
    """
    Classify API freshness based on cache age and worker status.

    Thresholds:
      - fresh:       cache_age < 50% of max age AND worker is ready
      - aging:       cache_age 50-100% of max age AND worker is ready
      - stale:       cache_age > max age OR worker status is "stale"
      - unavailable: no cache exists and no worker status

    Args:
        cache_age_seconds: Age of cache in seconds, or None if no cache
        cache_max_age_hours: Maximum acceptable cache age in hours
        worker_status: Worker status string ("ready", "stale") or None

    Returns:
        str: One of "fresh", "aging", "stale", "unavailable"
    """
    if cache_age_seconds is None and worker_status is None:
        return "unavailable"

    # Worker marked stale = always stale
    if worker_status == "stale":
        return "stale"

    if cache_age_seconds is None:
        return "unavailable"

    max_age_seconds = cache_max_age_hours * 3600
    half_max = max_age_seconds * 0.5

    if cache_age_seconds > max_age_seconds:
        return "stale"
    elif cache_age_seconds > half_max:
        return "aging"
    else:
        return "fresh"


def _format_age(seconds):
    """
    Format age in seconds to human-readable string.

    Examples:
        45 -> "45s"
        180 -> "3.0 min"
        7200 -> "2.0h"
        90000 -> "25.0h"
    """
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f} min"
    else:
        return f"{seconds / 3600:.1f}h"


def _format_time_ago(seconds):
    """
    Format seconds ago to human-readable relative time.

    Examples:
        30 -> "30s ago"
        180 -> "3 min ago"
        7200 -> "2h 0min ago"
        90000 -> "25h 0min ago"
    """
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.0f}s ago"
    elif seconds < 3600:
        return f"{seconds / 60:.0f} min ago"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}min ago"


def _format_timestamp(epoch_time):
    """Format epoch timestamp to GMT string."""
    if epoch_time is None:
        return "N/A"
    return time.strftime("%Y-%m-%d %H:%M:%S GMT", time.gmtime(epoch_time))


def _get_item_count(api_name, relay_set):
    """
    Get the count of items loaded for a given API from the relay_set data.

    Args:
        api_name: Internal API name
        relay_set: The Relays object

    Returns:
        int or None: Item count, or None if data unavailable
    """
    if api_name == "onionoo_details":
        if relay_set.json and relay_set.json.get("relays"):
            return len(relay_set.json["relays"])
    elif api_name == "onionoo_uptime":
        data = getattr(relay_set, "uptime_data", None)
        if data and "relays" in data:
            return len(data["relays"])
    elif api_name == "onionoo_bandwidth":
        data = getattr(relay_set, "bandwidth_data", None)
        if data and "relays" in data:
            return len(data["relays"])
    elif api_name == "aroi_validation":
        data = getattr(relay_set, "aroi_validation_data", None)
        if data and "results" in data:
            return len(data["results"])
    elif api_name == "collector_consensus":
        data = getattr(relay_set, "collector_consensus_data", None)
        if data and "relay_index" in data:
            return len(data["relay_index"])
    elif api_name == "collector_descriptors":
        data = getattr(relay_set, "collector_descriptors_data", None)
        if data and "all_seen_fingerprints" in data:
            return len(data["all_seen_fingerprints"])
    return None


def _get_extra_info(api_name, relay_set):
    """
    Get additional display info for specific APIs.

    Returns:
        str or None: Extra info string to display
    """
    if api_name == "collector_consensus":
        data = getattr(relay_set, "collector_consensus_data", None)
        if data and "votes" in data:
            vote_count = len(data["votes"])
            return f"from {vote_count} authority votes"
    elif api_name == "collector_descriptors":
        data = getattr(relay_set, "collector_descriptors_data", None)
        if data and "family_cert_fingerprints" in data:
            cert_count = len(data["family_cert_fingerprints"])
            return f"{cert_count:,} with family-cert"
    return None


def _is_api_enabled(api_name, enabled_apis):
    """
    Check if an API is enabled based on the --apis mode.

    Args:
        api_name: Internal API name
        enabled_apis: The --apis argument value ("details" or "all")

    Returns:
        bool: True if this API is enabled
    """
    # Details API is always enabled
    if api_name == "onionoo_details":
        return True

    # All other APIs require --apis=all
    if enabled_apis != "all":
        return False

    # Collector APIs also require consensus evaluation feature flag
    if api_name in ("collector_consensus", "collector_descriptors"):
        try:
            from .consensus import is_consensus_evaluation_enabled
            return is_consensus_evaluation_enabled()
        except Exception:
            return False

    return True


# ============================================================================
# MAIN DIAGNOSTICS COLLECTOR
# ============================================================================

def collect_api_diagnostics(relay_set, args):
    """
    Collect comprehensive diagnostics for all API data sources.

    Reads cache ages and worker statuses from the existing infrastructure
    (workers.py cache manager and state file) and builds a structured
    diagnostics object for template rendering.

    Args:
        relay_set: Relays instance with processed data
        args: argparse namespace with API URLs and --apis mode

    Returns:
        dict with keys:
          - apis: list of per-API diagnostics dicts
          - section_dependencies: list of section dependency dicts
          - overall_status: "fresh", "aging", "stale", or "unavailable"
          - overall_status_label: Human-readable status string
          - enabled_count: Number of enabled APIs
          - total_count: Total number of known APIs
          - site_generated: Formatted timestamp of site generation
    """
    now = time.time()
    enabled_apis = getattr(args, "enabled_apis", "all")
    worker_statuses = get_all_worker_status()

    api_diagnostics = []
    freshness_map = {}  # api_name -> freshness for dependency table

    for api_name, metadata in API_METADATA.items():
        enabled = _is_api_enabled(api_name, enabled_apis)

        # Get URL from args if available, otherwise use default
        url_arg = metadata.get("url_arg")
        if url_arg and hasattr(args, url_arg):
            url = getattr(args, url_arg)
        else:
            url = metadata["default_url"]

        # Get cache age
        cache_age = _cache_manager.get_cache_age(api_name)

        # Get worker status
        ws = worker_statuses.get(api_name, {})
        worker_status = ws.get("status") if ws else None
        worker_error = ws.get("error") if ws else None
        worker_timestamp = ws.get("timestamp") if ws else None

        # Classify freshness
        if not enabled:
            freshness = "unavailable"
        else:
            freshness = _classify_freshness(
                cache_age, metadata["cache_max_age_hours"], worker_status
            )

        freshness_map[api_name] = freshness

        # Get item count from relay_set
        item_count = _get_item_count(api_name, relay_set) if enabled else None
        extra_info = _get_extra_info(api_name, relay_set) if enabled else None

        # Cache age as percentage of max (for progress bar)
        max_age_seconds = metadata["cache_max_age_hours"] * 3600
        if cache_age is not None and max_age_seconds > 0:
            cache_pct = min(100.0, (cache_age / max_age_seconds) * 100)
        else:
            cache_pct = 0.0

        api_info = {
            "name": api_name,
            "display_name": metadata["display_name"],
            "url": url,
            "url_note": metadata.get("url_note", ""),
            "owner": metadata["owner"],
            "expected_frequency": metadata["expected_frequency"],
            "cache_max_age_hours": metadata["cache_max_age_hours"],
            "cache_max_age_display": f"{metadata['cache_max_age_hours']}h",
            "cache_age_seconds": cache_age,
            "cache_age_display": _format_age(cache_age),
            "cache_age_ago": _format_time_ago(cache_age),
            "cache_pct": round(cache_pct, 1),
            "cache_exceeded": cache_age is not None and cache_age > max_age_seconds,
            "worker_status": worker_status or "unknown",
            "worker_error": worker_error,
            "worker_timestamp": worker_timestamp,
            "worker_timestamp_display": _format_timestamp(worker_timestamp),
            "freshness": freshness,
            "item_count": item_count,
            "item_count_display": f"{item_count:,}" if item_count is not None else "N/A",
            "count_label": metadata["count_label"],
            "extra_info": extra_info,
            "enabled": enabled,
            "affected_sections": metadata["affected_sections"],
        }

        api_diagnostics.append(api_info)

    # Build section dependencies with freshness propagation
    section_deps = []
    for dep in SECTION_DEPENDENCIES:
        api_freshness_list = []
        for dep_api in dep["apis"]:
            api_freshness_list.append({
                "name": dep_api,
                "display_name": API_METADATA.get(dep_api, {}).get("display_name", dep_api),
                "short_name": _short_name(dep_api),
                "freshness": freshness_map.get(dep_api, "unavailable"),
            })

        # Worst status among dependencies (stale > aging > fresh > unavailable)
        worst = _worst_freshness([a["freshness"] for a in api_freshness_list])

        section_deps.append({
            "section": dep["section"],
            "apis": api_freshness_list,
            "worst_freshness": worst,
            "link": dep.get("link", ""),
            "link_label": dep.get("link_label", ""),
        })

    # Overall status
    all_freshness = [a["freshness"] for a in api_diagnostics if a["enabled"]]
    overall = _worst_freshness(all_freshness) if all_freshness else "unavailable"
    enabled_count = sum(1 for a in api_diagnostics if a["enabled"])

    if overall == "fresh":
        overall_label = f"ALL SYSTEMS FRESH -- {enabled_count}/{len(api_diagnostics)} Data Sources Healthy"
    elif overall == "aging":
        aging_count = sum(1 for f in all_freshness if f == "aging")
        overall_label = f"{aging_count} SOURCE{'S' if aging_count != 1 else ''} AGING -- Data approaching refresh"
    elif overall == "stale":
        stale_count = sum(1 for f in all_freshness if f == "stale")
        overall_label = f"{stale_count} STALE SOURCE{'S' if stale_count != 1 else ''} -- Some site data may be outdated"
    else:
        overall_label = "DATA SOURCES UNAVAILABLE"

    return {
        "apis": api_diagnostics,
        "section_dependencies": section_deps,
        "overall_status": overall,
        "overall_status_label": overall_label,
        "enabled_count": enabled_count,
        "total_count": len(api_diagnostics),
        "site_generated": getattr(relay_set, "timestamp", "Unknown"),
        "apis_mode": enabled_apis,
    }


def _short_name(api_name):
    """Get a short display name for dependency table pills."""
    short_names = {
        "onionoo_details": "Details",
        "onionoo_uptime": "Uptime",
        "onionoo_bandwidth": "Bandwidth",
        "aroi_validation": "AROI Validation",
        "collector_consensus": "Consensus",
        "collector_descriptors": "Descriptors",
    }
    return short_names.get(api_name, api_name)


def _worst_freshness(freshness_list):
    """
    Return the worst freshness from a list.

    Priority order (worst to best): stale > aging > unavailable > fresh
    """
    priority = {"stale": 0, "aging": 1, "unavailable": 2, "fresh": 3}
    if not freshness_list:
        return "unavailable"
    return min(freshness_list, key=lambda f: priority.get(f, 99))
