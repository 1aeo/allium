"""
File: site_generator.py

Site generation orchestration: defines what pages to generate and drives
the rendering pipeline. Extracted from allium.py for reusability.

To add a new page:
  - Add an entry to STANDALONE_PAGES, SORTED_PAGE_KEYS, or the sorted page definitions
  - That's it — the generation loops handle the rest

To add a new sorted-by variant (e.g., "by-latency"):
  - Add an entry to SORTED_BY_VARIANTS
"""

import os
from shutil import copytree

from .page_context import get_page_context, get_misc_page_context, StandardTemplateContexts


# =============================================================================
# PAGE DEFINITIONS (data-driven)
# =============================================================================

# Standalone pages: each is a single HTML file rendered from a template
# Format: (template, output_path, context_type, context_arg, extra_kwargs)
# context_type: 'index' = get_page_context, 'misc' = get_misc_page_context,
#               'health' = StandardTemplateContexts health, None = reuse prior
STANDALONE_PAGES = [
    # Main index (AROI leaderboards)
    {"template": "aroi-leaderboards.html", "output": "index.html",
     "context": "index", "label": "index page (AROI leaderboards)"},
    # Top 500 relays
    {"template": "index.html", "output": "top500.html",
     "context": "index", "is_index": True, "label": "top 500 relays page"},
    # All relays
    {"template": "all.html", "output": "misc/all.html",
     "context": "misc", "context_name": "All Relays", "label": "all relays page"},
    # AROI leaderboards (misc copy)
    {"template": "aroi-leaderboards.html", "output": "misc/aroi-leaderboards.html",
     "context": "misc", "context_name": "AROI Champions Dashboard", "label": "AROI leaderboards page"},
    # Network Health Dashboard
    {"template": "network-health-dashboard.html", "output": "network-health.html",
     "context": "health", "context_name": "Network Health Dashboard", "label": "network health dashboard"},
    # Directory Authorities
    {"template": "misc-authorities.html", "output": "misc/authorities.html",
     "context": "misc", "context_name": "Directory Authorities", "label": "directory authorities monitoring page"},
]

# Sorted-by variants for miscellaneous listing pages
SORTED_BY_VARIANTS = {
    "by-bandwidth": "1.bandwidth",
    "by-overall-bandwidth": "1.bandwidth",
    "by-guard-bandwidth": "1.guard_bandwidth",
    "by-middle-bandwidth": "1.middle_bandwidth",
    "by-exit-bandwidth": "1.exit_bandwidth",
    "by-bandwidth-mean": "1.bandwidth_mean",
    "by-consensus-weight": "1.consensus_weight_fraction",
    "by-guard-consensus-weight": "1.guard_consensus_weight_fraction",
    "by-middle-consensus-weight": "1.middle_consensus_weight_fraction",
    "by-exit-consensus-weight": "1.exit_consensus_weight_fraction",
    "by-exit-count": "1.exit_count",
    "by-guard-count": "1.guard_count",
    "by-middle-count": "1.middle_count",
    "by-unique-as-count": "1.unique_as_count",
    "by-unique-contact-count": "1.unique_contact_count",
    "by-unique-family-count": "1.unique_family_count",
    "by-first-seen": "1.first_seen",
    "by-total-data": "1.total_data",
}

# Miscellaneous sorted page types (each gets every sorted-by variant)
MISC_SORTED_PAGE_TYPES = [
    ("families", "Browse by Family"),
    ("networks", "Browse by Network"),
    ("contacts", "Browse by Contact"),
    ("countries", "Browse by Country"),
    ("platforms", "Browse by Platform"),
]

# Onionoo keys used to generate detail pages by unique value (e.g., AS43350)
# Ordered with slowest pages first (family, contact have most relays per group)
SORTED_PAGE_KEYS = [
    "family",
    "contact",
    "as",
    "country",
    "flag",
    "platform",
    "first_seen",
]


# =============================================================================
# SITE GENERATION
# =============================================================================

def generate_site(relay_set, args, progress_logger):
    """
    Generate the complete static site from processed relay data.
    
    This is the output stage of the pipeline:
      APIs → Processing → **Page Generation** (this function)
    
    Args:
        relay_set: Relays instance with fully processed data
        args: argparse namespace with output_dir, progress, etc.
        progress_logger: ProgressLogger instance for consistent progress tracking
    """
    # Path to the allium package directory (where static/ and templates/ live)
    allium_pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    progress_logger.log(f"Details API data loaded successfully - found {len(relay_set.json.get('relays', []))} relays")

    # Start page generation section
    progress_logger.start_section("Page Generation")

    # --- Standalone pages ---
    for page_def in STANDALONE_PAGES:
        progress_logger.log(f"Generating {page_def['label']}...")
        page_ctx = _build_page_context(page_def, relay_set)
        relay_set.write_misc(
            template=page_def["template"],
            path=page_def["output"],
            page_ctx=page_ctx,
            is_index=page_def.get("is_index", False),
        )
        progress_logger.log(f"Generated {page_def['label']}")

    # --- Miscellaneous sorted pages ---
    progress_logger.log("Generating miscellaneous sorted pages...")
    for suffix, sorted_by in SORTED_BY_VARIANTS.items():
        for page_type, page_title in MISC_SORTED_PAGE_TYPES:
            standard_contexts = StandardTemplateContexts(relay_set)
            page_ctx = standard_contexts.get_misc_page_context(
                f"misc-{page_type}.html", page_title, sorted_by=sorted_by
            )
            relay_set.write_misc(
                template=f"misc-{page_type}.html",
                path=f"misc/{page_type}-{suffix}.html",
                sorted_by=sorted_by,
                page_ctx=page_ctx,
            )
    progress_logger.log(f"Generated {len(MISC_SORTED_PAGE_TYPES)} miscellaneous sorted pages")

    # --- Detail pages by key (family, contact, as, country, flag, platform, first_seen) ---
    for key in SORTED_PAGE_KEYS:
        relay_set.write_pages_by_key(key)

    # --- Individual relay pages ---
    progress_logger.log("Generating individual relay info pages...")
    relay_set.write_relay_info()
    progress_logger.log(f"Generated individual pages for {len(relay_set.json.get('relays', []))} relays")

    # --- Static files ---
    progress_logger.log("Copying static files...")
    static_src = os.path.join(allium_pkg_dir, "static")
    static_dst = os.path.join(args.output_dir, "static")
    if not os.path.exists(static_dst):
        copytree(static_src, static_dst)
        progress_logger.log("Copied static files to output directory")
    else:
        progress_logger.log("Static files already exist, skipping copy")

    # --- Search index ---
    progress_logger.log("Generating search index...")
    from .search_index import generate_search_index
    search_index_path = os.path.join(args.output_dir, "search-index.json")
    search_stats = generate_search_index(
        relay_set.json, search_index_path,
        validated_aroi_domains=getattr(relay_set, 'validated_aroi_domains', None)
    )
    progress_logger.log(
        f"Generated search index: {search_stats['relay_count']} relays, "
        f"{search_stats['family_count']} families, {search_stats['file_size_kb']} KB"
    )

    # End page generation section
    progress_logger.end_section("Page Generation")
    progress_logger.log("Allium static site generation completed successfully!")


def _build_page_context(page_def, relay_set):
    """Build the appropriate page context based on page definition."""
    ctx_type = page_def.get("context")
    
    if ctx_type == "index":
        return get_page_context('index', 'home')
    elif ctx_type == "misc":
        return get_misc_page_context(page_def["context_name"])
    elif ctx_type == "health":
        standard_contexts = StandardTemplateContexts(relay_set)
        return standard_contexts.get_index_page_context(
            page_def["context_name"], relay_set.timestamp
        )
    else:
        return get_page_context('misc', None)
