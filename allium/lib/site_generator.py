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

import filecmp
import os
import re
from shutil import copy2

from .page_context import get_page_context, get_misc_page_context, StandardTemplateContexts
from .page_writer import (
    RELAY_PAGE_SIZE,
    paginated_filename,
    pagination_context,
    write_misc,
    write_pages_by_key,
    write_relay_info,
)


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
     "context": "misc", "context_name": "All Relays", "label": "all relays page",
     "paginate": True},
    # AROI leaderboards (misc copy)
    {"template": "aroi-leaderboards.html", "output": "misc/aroi-leaderboards.html",
     "context": "misc", "context_name": "AROI Champions Dashboard", "label": "AROI leaderboards page"},
    # Network Health Dashboard
    {"template": "network-health-dashboard.html", "output": "network-health.html",
     "context": "health", "context_name": "Network Health Dashboard", "label": "network health dashboard"},
    # Directory Authorities
    {"template": "misc-authorities.html", "output": "misc/authorities.html",
     "context": "misc", "context_name": "Directory Authorities", "label": "directory authorities monitoring page"},
    # API Diagnostics
    {"template": "api-diagnostics.html", "output": "misc/diagnostics.html",
     "context": "misc", "context_name": "API Diagnostics", "label": "API diagnostics page"},
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

MISC_PAGE_DATA_KEYS = {
    "families": "family",
    "networks": "as",
    "contacts": "contact",
    "countries": "country",
    "platforms": "platform",
}

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

def _remove_stale_pagination_files(output_dir, base_filename):
    """Remove page 2+ files left by an earlier, longer generated listing."""
    if not os.path.isdir(output_dir):
        return 0
    stem, extension = os.path.splitext(base_filename)
    page_name = re.compile(
        rf"^{re.escape(stem)}-page-(?:[2-9]|[1-9][0-9]+)"
        rf"{re.escape(extension)}$"
    )
    removed = 0
    for filename in os.listdir(output_dir):
        if not page_name.match(filename):
            continue
        path = os.path.join(output_dir, filename)
        if os.path.isfile(path):
            os.remove(path)
            removed += 1
    return removed


def _deduplicate_family_listing_items(listing_items, relay_rows):
    """Preserve the legacy cross-family relay de-duplication before paging."""
    processed_fingerprints = set()
    deduplicated_items = []
    for item in listing_items:
        relay_indexes = item[1].get("relays", [])
        if not relay_indexes:
            continue
        first_fingerprint = relay_rows[relay_indexes[0]].get("fingerprint")
        if first_fingerprint in processed_fingerprints:
            continue
        deduplicated_items.append(item)
        processed_fingerprints.update(
            relay_rows[index].get("fingerprint") for index in relay_indexes
        )
    return deduplicated_items


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

    # Compute API diagnostics data before page generation
    from .api_diagnostics import collect_api_diagnostics
    relay_set.api_diagnostics = collect_api_diagnostics(relay_set, args)

    # Start page generation section
    progress_logger.start_section("Page Generation")

    # --- Standalone pages ---
    for page_def in STANDALONE_PAGES:
        progress_logger.log(f"Generating {page_def['label']}...")
        page_ctx = _build_page_context(page_def, relay_set)
        if page_def.get("paginate"):
            relay_rows = relay_set.json.get("relays", [])
            total_pages = max(
                1, (len(relay_rows) + RELAY_PAGE_SIZE - 1) // RELAY_PAGE_SIZE
            )
            output_dir, base_filename = os.path.split(page_def["output"])
            _remove_stale_pagination_files(
                os.path.join(args.output_dir, output_dir), base_filename
            )
            for page_number in range(1, total_pages + 1):
                filename = paginated_filename(base_filename, page_number)
                output = os.path.join(output_dir, filename)
                start = (page_number - 1) * RELAY_PAGE_SIZE
                write_misc(
                    relay_set,
                    template=page_def["template"],
                    path=output,
                    page_ctx=page_ctx,
                    is_index=page_def.get("is_index", False),
                    relay_subset=relay_rows[start:start + RELAY_PAGE_SIZE],
                    pagination=pagination_context(
                        base_filename, page_number, total_pages
                    ),
                    page_number=page_number,
                )
        else:
            write_misc(
                relay_set,
                template=page_def["template"],
                path=page_def["output"],
                page_ctx=page_ctx,
                is_index=page_def.get("is_index", False),
            )
        progress_logger.log(f"Generated {page_def['label']}")

    # --- Miscellaneous sorted pages ---
    progress_logger.log("Generating miscellaneous sorted pages...")
    standard_contexts = StandardTemplateContexts(relay_set)
    for suffix, sorted_by in SORTED_BY_VARIANTS.items():
        for page_type, page_title in MISC_SORTED_PAGE_TYPES:
            # misc-contacts and misc-families have no unique-contact/
            # unique-family columns; the variants sorted by them gave no
            # visual indication of the sort, so they are not generated.
            if (page_type in ("contacts", "families")
                    and suffix in ("by-unique-contact-count",
                                   "by-unique-family-count")):
                continue
            page_ctx = standard_contexts.get_misc_page_context(
                f"misc-{page_type}.html", page_title, sorted_by=sorted_by
            )
            data_key = MISC_PAGE_DATA_KEYS[page_type]
            listing_items = list(
                relay_set.json.get("sorted", {}).get(data_key, {}).items()
            )
            sort_field = sorted_by.split(",", 1)[0].split(".", 1)[1]
            listing_items.sort(
                key=lambda item: item[1].get(sort_field, 0), reverse=True
            )
            if page_type == "families":
                # The legacy single-page template suppresses overlapping
                # effective-family groups by remembering every relay already
                # emitted. Do that once before slicing so the de-duplication
                # state is preserved across pagination boundaries.
                listing_items = _deduplicate_family_listing_items(
                    listing_items, relay_set.json.get("relays", [])
                )
            total_pages = max(
                1, (len(listing_items) + RELAY_PAGE_SIZE - 1) // RELAY_PAGE_SIZE
            )
            base_filename = f"{page_type}-{suffix}.html"
            _remove_stale_pagination_files(
                os.path.join(args.output_dir, "misc"), base_filename
            )
            for page_number in range(1, total_pages + 1):
                start = (page_number - 1) * RELAY_PAGE_SIZE
                filename = paginated_filename(base_filename, page_number)
                write_misc(
                    relay_set,
                    template=f"misc-{page_type}.html",
                    path=f"misc/{filename}",
                    sorted_by=sorted_by,
                    page_ctx=page_ctx,
                    listing_items=listing_items[start:start + RELAY_PAGE_SIZE],
                    pagination=pagination_context(
                        base_filename, page_number, total_pages
                    ),
                    page_number=page_number,
                )
    progress_logger.log(f"Generated {len(MISC_SORTED_PAGE_TYPES)} miscellaneous sorted pages")

    # --- Detail pages by key (family, contact, as, country, flag, platform, first_seen) ---
    for key in SORTED_PAGE_KEYS:
        write_pages_by_key(relay_set, key)

    # --- Individual relay pages ---
    progress_logger.log("Generating individual relay info pages...")
    write_relay_info(relay_set)
    progress_logger.log(f"Generated individual pages for {len(relay_set.json.get('relays', []))} relays")

    # --- Static files ---
    progress_logger.log("Syncing static files...")
    static_src = os.path.join(allium_pkg_dir, "static")
    static_dst = os.path.join(args.output_dir, "static")
    copied, skipped = _sync_static_files(static_src, static_dst)
    progress_logger.log(f"Static files: {copied} updated, {skipped} unchanged")

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

    # --- Prometheus metrics ---
    progress_logger.log("Generating Prometheus metrics...")
    from .prometheus_metrics import generate_prometheus_metrics
    prom_stats = generate_prometheus_metrics(relay_set, args.output_dir)
    prom_msg = (
        f"Generated Prometheus metrics: {prom_stats['exit_relays']} exits, "
        f"{prom_stats['aroi_relays']} AROI, {prom_stats['file_size_kb']} KB"
    )
    if not prom_stats["dns_available"]:
        prom_msg += " [DNS source unavailable]"
    if not prom_stats["aroi_available"]:
        prom_msg += " [AROI source unavailable]"
    progress_logger.log(prom_msg)

    # --- Search-engine discovery files ---
    progress_logger.log("Generating search-engine discovery files...")
    from .search_discovery import generate_search_discovery
    from .seo import (
        oversized_html_files,
        rewrite_internal_html_links,
    )
    link_stats = rewrite_internal_html_links(args.output_dir)
    progress_logger.log_without_increment(
        f"Rewrote {link_stats['changed_links']} internal .html link(s) "
        f"across {link_stats['changed_files']} file(s) to clean routes"
    )
    discovery_stats = generate_search_discovery(
        args.output_dir, args.base_url
    )
    if discovery_stats["generated"]:
        progress_logger.log(
            f"Generated {discovery_stats['sitemap_count']} sitemap file(s) "
            f"with {discovery_stats['url_count']} canonical URLs; "
            f"excluded {discovery_stats['noindex_count']} noindex page(s)"
        )
    else:
        progress_logger.log(
            "Skipped search-engine discovery files for non-production base URL"
        )

    # Protect crawlers from silently regressing to multi-megabyte HTML pages.
    oversized = oversized_html_files(args.output_dir)
    if oversized:
        preview = ", ".join(
            f"{path} ({size:,} bytes)" for path, size in oversized[:10]
        )
        raise RuntimeError(
            f"{len(oversized)} generated HTML file(s) exceed the "
            f"1,900,000-byte crawl-size guard: {preview}"
        )
    progress_logger.log_without_increment(
        "HTML crawl-size guard passed (all pages <= 1,900,000 bytes)"
    )

    # End page generation section
    progress_logger.end_section("Page Generation")
    progress_logger.log("Allium static site generation completed successfully!")


def _sync_static_files(src_dir, dst_dir):
    """Copy only new or changed files from src_dir to dst_dir.

    A file is copied when the destination is missing, the size differs,
    the source mtime is newer, or byte content differs (same size/mtime
    can still diverge after checkout or archive extraction).  Returns
    (copied, skipped) counts.
    """
    copied = skipped = 0
    for dirpath, _dirnames, filenames in os.walk(src_dir):
        rel_dir = os.path.relpath(dirpath, src_dir)
        dst_subdir = os.path.join(dst_dir, rel_dir)
        os.makedirs(dst_subdir, exist_ok=True)

        for fname in filenames:
            src_file = os.path.join(dirpath, fname)
            dst_file = os.path.join(dst_subdir, fname)

            if os.path.isfile(dst_file):
                src_stat = os.stat(src_file)
                dst_stat = os.stat(dst_file)
                if (src_stat.st_size == dst_stat.st_size
                        and src_stat.st_mtime <= dst_stat.st_mtime
                        and filecmp.cmp(src_file, dst_file, shallow=False)):
                    skipped += 1
                    continue

            copy2(src_file, dst_file)
            copied += 1

    return copied, skipped


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
