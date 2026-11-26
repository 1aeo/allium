# Multiprocessing Architecture

**Audience**: Contributors  
**Scope**: Fork-based parallel precomputation, page generation, and SEO HTML post-processing

Allium uses Python's `multiprocessing` module with `fork()` context (`fork_map()` in `allium/lib/worker_pool.py`) to parallelize expensive data precomputation, HTML page rendering, and bulk HTML post-processing with copy-on-write memory sharing across worker processes.

---

## Architecture

### Two-Phase Precomputation and Rendering

Contact and family pages depend on expensive per-group calculations (rankings, reliability statistics, AROI validation cascades, network position, and Exit DNS Health summaries). Allium precomputes these during data processing before forking rendering workers:

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA PROCESSING PHASE                       │
├─────────────────────────────────────────────────────────────────┤
│  1. Parallel Contact & Family Precomputation (lib/relays.py)    │
│     ├── _precompute_all_contact_page_data()                     │
│     ├── _precompute_all_family_page_data()                      │
│     ├── fork_map() (ProcessPoolExecutor with fork context)      │
│     ├── Results streamed as chunks complete                     │
│     └── Stored directly on group dicts (flat storage)           │
│                                                                 │
│  Contact precomputed fields:                                    │
│     • contact_rankings, operator_reliability                    │
│     • contact_display_data, contact_validation_status           │
│     • aroi_validation_timestamp, is_validated_aroi, aroi_domain │
│     • precomputed_bandwidth_unit, exit_dns_health_summary       │
│                                                                 │
│  Family precomputed fields:                                     │
│     • contact_validation_status, network_position               │
│     • family_support_counts, exit_dns_health_summary            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PAGE GENERATION PHASE                       │
├─────────────────────────────────────────────────────────────────┤
│  2. Parallel Page Rendering (lib/page_writer.py)                │
│     ├── gc.freeze() freezes relay heap before forking           │
│     ├── fork_map() shares templates and relay_set via fork()    │
│     └── Each worker renders and writes pages independently      │
│                                                                 │
│  Applies to: family, contact, as, country, flag, platform,      │
│  first_seen (threshold: 100+ output files), and relay-info      │
│  pages (threshold: 100+ relays)                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   POST-GENERATION HTML PASSES                   │
├─────────────────────────────────────────────────────────────────┤
│  3. Parallel SEO HTML Passes (lib/seo.py, search_discovery.py)  │
│     ├── map_html_files() via fork_map() (threshold: 256+ files) │
│     ├── rewrite_internal_html_links() for pre-existing HTML     │
│     └── _head_signals() extracts canonical/noindex for sitemap  │
└─────────────────────────────────────────────────────────────────┘
```

### Why Two Phases?

Contact and family pages require per-group calculations (AROI validation status, operator rankings, reliability statistics) that would otherwise be repeated across rendered pages or variants. Precomputing them once and storing results on `contact_data` and `family_data` avoids redundant calculation, keeps peak memory bounded by streaming results as they arrive, and turns page generation into pure template rendering.

---

## Implementation Details

### Worker Initialization

Page-rendering workers receive shared data through `fork()` copy-on-write (`lib/page_writer.py`):

```python
# Multiprocessing globals (initialized via fork for copy-on-write memory sharing)
_mp_relay_set = None
_mp_template = None
_mp_page_type = None
_mp_the_prefixed = None
_mp_validated_aroi_domains = None
_mp_output_root = None

def _init_mp_worker(relay_set, template, page_type=None, the_prefixed=None, validated_aroi_domains=None, output_root=None):
    """Initialize worker with shared data via fork"""
    global _mp_relay_set, _mp_template, _mp_page_type, _mp_the_prefixed, _mp_validated_aroi_domains, _mp_output_root
    _mp_relay_set = relay_set
    _mp_template = template
    _mp_page_type = page_type
    _mp_the_prefixed = the_prefixed if the_prefixed is not None else []
    _mp_validated_aroi_domains = validated_aroi_domains if validated_aroi_domains is not None else set()
    _mp_output_root = output_root
```

### Precomputation Workers

Contact and family precomputation share DRY helpers (`_compute_contact_predata` and `_compute_family_predata` in `lib/page_writer.py`) across both sequential and parallel paths:

```python
def _precompute_contact_worker(args):
    """Precompute data for a single contact in worker process."""
    contact_hash, aroi_validation_timestamp, validated_aroi_domains = args

    try:
        result = _compute_contact_predata(
            _precompute_relay_set, contact_hash, aroi_validation_timestamp, validated_aroi_domains)
    except Exception:
        return (contact_hash, None)
    return (contact_hash, _dump_precomputed(result) if result else None)

def _precompute_family_worker(args):
    """Precompute data for a single family in worker process."""
    family_hash, = args

    try:
        result = _compute_family_predata(_precompute_relay_set, family_hash)
    except Exception:
        return (family_hash, None)
    return (family_hash, _dump_precomputed(result) if result else None)
```

### Streaming Results

`Relays._precompute_contacts_parallel()` and `Relays._precompute_families_parallel()` (in `lib/relays.py`) iterate `fork_map()` as results arrive to lower peak memory and report progress:

```python
def _precompute_contacts_parallel(self, contact_hashes, aroi_validation_timestamp, validated_aroi_domains):
    worker_args = [(contact_hash, aroi_validation_timestamp, validated_aroi_domains)
                   for contact_hash in contact_hashes]

    total_contacts = len(contact_hashes)
    processed = 0
    chunk_size = max(50, total_contacts // (self.mp_workers * 4))

    for contact_hash, precomputed_data in fork_map(
        self.mp_workers, _precompute_contact_worker, worker_args, chunk_size, _init_precompute_worker, (self,)
    ):
        if precomputed_data and contact_hash in self.json["sorted"]["contact"]:
            contact_data = self.json["sorted"]["contact"][contact_hash]
            for key, value in _load_precomputed(precomputed_data, self.json["relays"]).items():
                contact_data[key] = value

        processed += 1
        if processed % 500 == 0:
            self.progress_logger.log_without_increment(f"Pre-computed {processed}/{total_contacts} contacts...")
```

### Parallel SEO HTML Link-Rewriting and Head Parsing

Pages written during a run have internal `.html` hrefs converted to clean routes in memory by `_write_html()` (`lib/page_writer.py`). For any pre-existing HTML files left in `--out` from earlier runs (`modified_before=progress_logger.start_time`), `lib/site_generator.py` runs `rewrite_internal_html_links()` (`lib/seo.py`), which calls `map_html_files()` to distribute file rewrites across up to `min(8, os.cpu_count() or 1)` forked workers when `len(html_paths) >= 256`. `generate_search_discovery()` (`lib/search_discovery.py`) uses the same `map_html_files()` pool to extract `<head>` canonical and `robots` directives when building `sitemap.xml`.

### Flat Storage Pattern

Precomputed data is stored directly on `contact_data` and `family_data` for direct lookup in `build_template_args()` (`lib/page_writer.py`):

```python
# Storing (in precomputation)
contact_data["contact_rankings"] = rankings
contact_data["operator_reliability"] = reliability
contact_data["is_validated_aroi"] = True

# Accessing (in build_template_args)
if k == "contact":
    contact_rankings = i.get("contact_rankings", [])
    operator_reliability = i.get("operator_reliability")
    is_validated_aroi = i.get("is_validated_aroi", False)
```

### Sharing Relay Data With Workers

- **Precompute results reference relays by index.** Contact and family results embed the group's relay dicts (validation status entries point at them). Workers pickle each shared relay dict as its index in `relay_set.json["relays"]` and the parent re-links its own dict (`_dump_precomputed` / `_load_precomputed`), matching the sequential path. Sending full copies would cost ~29GB of pickles per run because family groups list every member once per member.
- **The heap is frozen before rendering.** `allium.py` pauses cyclic GC while data is fetched and processed (the data holds almost no cycles), then calls `gc.freeze()` before `generate_site()` so collections in the parent and forked workers skip the multi-GB dataset instead of re-traversing it.
- **Relay rows are memoized per process.** `contact-relay-list.html` renders each row as a cached `relay_row_head` (`_cached_relay_row_head`, keyed on everything the macro reads) plus an uncached `relay_row_tail` holding cells that depend on the current time.

---

## Configuration

### Command Line Options

```bash
# Default: auto-detected CPU count, minimum 4 workers
python3 allium/allium.py --out ./www --progress

# Custom worker count
python3 allium/allium.py --out ./www --workers 8

# Disable multiprocessing
python3 allium/allium.py --out ./www --workers 0
```

### Multiprocessing Thresholds

| Setting | Default | Description |
|---------|---------|-------------|
| `--workers` | `max(4, os.cpu_count() or 4)` | Parallel workers for precomputation and page generation |
| Precompute / page threshold | 100 | Minimum contacts/families, output files, or relays to fork workers |
| SEO HTML pool workers | `min(8, os.cpu_count() or 1)` | Forked workers used by `map_html_files()` (`lib/seo.py`) |
| SEO HTML pool threshold | 256 | Minimum HTML files before `map_html_files()` forks workers |
| Precompute chunk size | 50+ | Minimum chunk size for contact/family precomputation |

---

## Platform Compatibility

### Fork Context (Linux/macOS)

The implementation uses `fork()` context for copy-on-write memory sharing. `fork_map()` (in `allium/lib/worker_pool.py`) runs every pool. The function, items, and `initargs` reach the workers through `fork()` and are never pickled; only item indexes cross the call queue:

```python
for result in fork_map(workers, worker_func, items, chunksize, initializer, initargs):
    ...
```

Two `ProcessPoolExecutor` pitfalls are handled in `fork_map()`:

- Chunks of the items themselves could fill the call queue's 64 KiB pipe. A worker death then hangs Python 3.9/3.10 (CPython gh-94777) instead of raising `BrokenProcessPool`. Chunk sizes are capped (`min(chunksize, 8192 // (workers + 1))`) so chunks of indexes stay below that limit.
- Executor workers wait forever when their parent dies, each holding its copy of the relay set. A daemon watchdog thread (`_exit_with_parent`) in every worker exits once the parent is gone.

One case still hangs on every Python version: a worker killed while its result is only partly written to the result pipe (precompute chunk results are up to a few MB) leaves the executor waiting for the rest of that message instead of raising `BrokenProcessPool`. Killing the hung build still stops its workers.

### Fallback Behavior

If multiprocessing fails or isn't available (Windows), the code falls back to sequential processing:

```python
use_mp = relay_set.mp_workers > 0 and output_files >= 100

if use_mp:
    write_pages_parallel(...)
else:
    # Sequential fallback
    for v in sorted_values:
        ...
```

Every pool uses `ProcessPoolExecutor` rather than `multiprocessing.Pool`. A `Pool` replaces a worker that dies abruptly (OOM killer, segfault) without failing its task, so `map()` / `imap_unordered()` would wait forever. `ProcessPoolExecutor` raises `BrokenProcessPool` instead, triggering the sequential fallback: every page of the set is rendered again, or every group precomputed again (while `map_html_files()` finishes remaining HTML files in-process). Tests in `tests/unit/test_relay_page_parallel.py`, `tests/unit/test_seo.py`, `tests/unit/test_worker_pool.py`, and `tests/integration/test_parallel_generation.py` kill a worker in each pool or the parent of a pool.

---

## Troubleshooting

### Common Issues

**Issue**: `fork()` context not available on Windows

**Solution**: Multiprocessing is disabled on Windows; sequential processing is used instead.

---

**Issue**: OOM (Out of Memory) during parallel processing

**Solution**: Reduce worker count with `--workers 2` or disable with `--workers 0`.

---

**Issue**: Missing contact metadata after generation

**Solution**: Verify `Relays.enrich_with_api_data()` calls `_precompute_all_contact_page_data()` and `_precompute_all_family_page_data()` before `generate_site()`.

---

## How to Verify

Run the contact multiprocessing regression tests in `tests/integration/test_contact_template.py` (`TestContactMultiprocessingRegression`, covering `test_contact_precomputation_stores_required_metadata`, `test_contact_page_multiprocessing_preserves_metadata`, `test_build_template_args_uses_flat_storage`, and `test_precomputation_stores_aroi_domain_for_vanity_urls`) plus the pool and parallel generation suites:

```bash
# Run multiprocessing regression tests
python3 -m pytest tests/integration/test_contact_template.py::TestContactMultiprocessingRegression -v

# Run all contact template tests
python3 -m pytest tests/integration/test_contact_template.py -v

# Run worker pool, parallel relay-page, SEO pool, and parallel generation tests
python3 -m pytest tests/unit/test_worker_pool.py tests/unit/test_relay_page_parallel.py tests/unit/test_seo.py tests/integration/test_parallel_generation.py -v
```

---

## Future Improvements

- Adaptive worker count based on system resources
- Shared memory for large datasets to reduce fork overhead
- Progress bars for individual page types

---

**Related**: [Architecture Overview](overview.md) | [Configuration](../user-guide/configuration.md)
