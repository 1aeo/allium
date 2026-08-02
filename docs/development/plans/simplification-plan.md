# Plan 1: Simplification Plan

Scope: reduce architectural complexity — fewer layers, fewer parallel ways of doing the
same thing — while producing byte-identical output (modulo the known noise floor).
This plan is about structure; raw line deletion is covered by the LOC reduction plan,
and behavior changes by the bug fix plan.

## Workflow (applies to every phase)

```bash
# 1. Baseline BEFORE the change (full APIs)
python3 allium/allium.py --out allium/www_baseline --apis all --progress

# 2. Apply one phase of refactoring

# 3. Regenerate AFTER the change
python3 allium/allium.py --out allium/www_after --apis all --progress

# 4. Compare all ~28k files
python3 compare_outputs.py --quiet

# 5. Tests + lint
pytest
flake8 . --select=E9,F63,F7,F82 --show-source
```

Verified environment facts: a full run takes ~3.5 min / ~7 GB RSS; two back-to-back
runs with warm caches diff at a noise floor of ~25 content files (uptime ticking on
relay pages, timestamps on root pages). **Every phase in this plan must diff at the
noise floor** — simplification must not change output. Any diff above the floor means
the refactor altered behavior and must be fixed before the phase is committed.

Phases are ordered so that each one reduces the surface area the next one touches.

---

## Phase 1 — Single escaping strategy (do the bug-fix first)

Templates render with `autoescape=True` while Python pre-escapes a dozen `*_escaped`
fields, which currently double-escapes output (see bug fix plan, Phase 1). Resolve that
first. Decision recorded there: escaping logic **stays in Python** (Jinja2 is slower;
templates should render precomputed values) — the pre-escaped fields are wrapped in
`markupsafe.Markup` so autoescape does not re-escape them, and autoescape remains on as
the safety net for raw fields.

Then collapse `html_escape_utils.py` (411 lines, 5 classes) into a small module:

- Production only uses `create_bulk_escaper()` (from `relays.py`) and two constants.
  `HTMLEscapeConstants`, `HTMLEscaper`, `RelayFieldEscaper`, `TemplateEscapingHelpers`,
  `escape_relay_field`, `create_template_helpers` are unused indirection.
- Replace with module-level functions: one `escape_relay_fields(relay)` (returning
  `Markup`-wrapped escaped fields) plus `safe_html_escape(value, fallback)`.

**Risk:** low. **Diff:** noise floor only (after the escaping bug fix has landed).

---

## Phase 2 — One error-handling/cache-fallback layer for API workers

Today there are two overlapping layers:

- `workers._fetch_with_cache_fallback` handles timeout/parse/validation errors with
  cache fallback, keyed by `config.api_name`.
- `error_handlers.handle_http_errors` decorator wraps the same functions to handle
  304/HTTP/network errors with its own cache fallback — keyed (incorrectly) by display
  name, plus a fragile positional-args inspection to find the progress logger.

Simplification:

1. Move the 304 and HTTP-error handling **into** `_fetch_with_cache_fallback`, where
   `config.api_name`, `cached_data`, and `log_progress` already exist. The decorator
   and its `cache_loader`/`mark_ready`/`mark_stale` parameters disappear.
2. Delete `handle_worker_errors` (never applied anywhere; `coordinator._run_worker`
   already has equivalent inline handling) and the now-unused imports in
   `coordinator.py`.
3. The per-fetcher `log_wrapper` closures in `workers.py` (repeated 5×) collapse into
   `_fetch_with_cache_fallback`'s existing `log_progress`.

**Risk:** medium — error paths are hard to exercise; add unit tests for 304-with-cache,
304-without-cache, HTTPError-5xx, URLError before refactoring. **Diff:** noise floor
(happy path unchanged).

---

## Phase 3 — One API registry

`coordinator.py` defines `API_WORKER_REGISTRY`, while `workers.py` separately defines
per-API `APIConfig` objects, display names, and orphan fetchers that are not in the
registry (`fetch_consensus_health`, legacy `fetch_collector_data`). The consensus-health
path is wired through `coordinator.get_consensus_health_data()` → always `None` →
stored on `relay_set` → never read.

Simplification:

1. Make `APIConfig` the single source of truth: add `worker_fn`, `enabled_flag`, and
   `progress_name` fields; derive `API_WORKER_REGISTRY` from the config list.
2. Keep the consensus-health path (`fetch_consensus_health`,
   `get_consensus_health_data`, the `consensus_health_data` attach in
   `coordinator.create_relay_set_with_coordinator`, and the reader stub in `relays.py`)
   — it is a planned feature path, not cruft. When migrating to the unified registry,
   give it an `APIConfig` entry with a disabled/optional flag so it fits the single
   registry instead of remaining an orphan.
3. Delete `Coordinator.get_collector_data` (tests-only) and the unused
   `self.workers = {}`.

**Risk:** medium — coordinator tests reference some of these; update tests rather than
keeping dead production code. **Diff:** noise floor.

---

## Phase 4 — Collapse the progress-logging stack

Three generations of progress APIs coexist: `ProgressLogger.log/log_without_increment`,
legacy module functions (`log_step_progress`, `log_progress_with_step_increment` — zero
callers), coordinator-internal `_log_progress` / `_log_progress_with_step_increment` /
`_log_progress_without_increment`, plus `relays.py` manually incrementing
`self.progress_step` that the coordinator then overwrites.

Simplification:

1. Keep only `ProgressLogger.log()` / `log_without_increment()`; delete legacy module
   functions and `create_child_logger` / `update_from_other_logger` (zero callers).
2. Thread one `ProgressLogger` instance through coordinator → relays → page_writer;
   remove the manual `progress_step` bookkeeping and the `[step/total]` counters being
   passed as separate ints.
3. Derive `total_steps` in `allium.py` from the enabled API count and page-generation
   step list instead of hard-coded `4 + 22 + 35` with stale comments (run logs `[61/61]`
   while the comment says 59).

**Risk:** low — progress output is cosmetic, but keep the log format identical to make
CI log diffs stable. **Diff:** none (progress goes to stdout, not HTML).

---

## Phase 5 — Remove the `Relays` god-object facade

`relays.py` has ~40 one-line delegate methods (lines ~895–1393) that forward to
`categorization`, `page_writer`, `uptime_utils`, etc. Callers mix direct module calls
and `relay_set._method()` calls arbitrarily, so every new module function grows a
facade twin.

Simplification:

1. Inventory delegates; for each, migrate call sites to the underlying module function
   (passing `relay_set` explicitly) and delete the wrapper. Do it in 3–4 batches
   (categorization, uptime/bandwidth, page-writer, misc) with a full diff after each.
2. Keep genuinely stateful methods (`_preprocess_template_data`, cache fields) on the
   class.
3. Delete `Relays._write_timestamp` and `Relays.create_output_dir` (zero callers).

**Risk:** medium — many call sites, including the multiprocessing worker init path in
`page_writer.py` which pickles `relay_set`; verify parallel contact-page rendering still
works (run with default worker count and confirm in progress output). **Diff:** noise
floor.

---

## Phase 6 — Unify the sequential/parallel page-writing paths

`page_writer.write_pages_by_key` routes contact pages to dedicated renderers and returns
early (`if k == "contact": return`), yet the generic sequential loop below still carries
~130 lines of contact-only logic that can never execute, and `write_pages_parallel`
carries an unreachable contact vanity-URL block.

Simplification:

1. Delete the unreachable contact branches from the generic paths.
2. Extract the shared "build template args for one page" logic used by sequential and
   parallel paths into one function (the `_get_family_support_counts` /
   `_get_exit_dns_health_summary` helpers already started this) so the two paths cannot
   drift.
3. Move `get_directory_authorities_data`'s live `AuthorityMonitor` TCP probing out of
   page rendering into a coordinator worker, so page generation is pure rendering.
   (Do this last; it changes when probes run, not what is rendered.)

**Risk:** step 1–2 low; step 3 medium (timing of probes changes; authorities page
content may legitimately differ — review that diff explicitly). **Diff:** steps 1–2
noise floor; step 3 authorities page only.

---

## Phase 7 — Consolidate overlapping stats/formatting utilities

Three module families compute the same things:

- **Statistics:** `statistical_utils.py`, plus wrappers in `uptime_utils.py` and CV
  logic in `bandwidth_utils.py`. Keep `StatisticalUtils` as the only implementation;
  everything else calls it.
- **Bandwidth formatting:** `BandwidthFormatter` class (stateless except `use_bits`),
  `relay_diagnostics._format_rate`, `consensus_evaluation._format_bandwidth_display`.
  Make the formatter module-level functions parameterized by `use_bits`; delete the
  duplicate private formatters.
- **Overload/stability:** `stability_utils.compute_relay_stability` and
  `relay_diagnostics._check_overload_issues` duplicate overload detection with slightly
  different semantics (the 72h window is applied inconsistently — see bug plan
  Phase 8). One `evaluate_overload(relay, now)` used by both.
- **Time-ago formatting:** `api_diagnostics._format_age/_format_time_ago/_format_timestamp`
  duplicate `time_utils`. Reuse `time_utils` with thin wrappers only where the display
  string genuinely differs.
- **URL-token regexes:** three near-identical regexes in `aroileaders.py`,
  `aroi_validation.py`, `categorization.py`; move one shared pattern into
  `string_utils.py`.

**Risk:** medium — formatting differences show up immediately in the diff, which is
exactly the point; review any diff character-by-character before accepting. **Diff:**
must be noise floor; if a diff appears, the two implementations disagreed and the plan
is to preserve the behavior the templates currently show (byte-identical), then decide
separately (bug plan) if that behavior was wrong.

---

## Phase 8 — Template deduplication

1. **`misc-*.html` family (5 files, ~750 lines, ~60% duplicated):** extract
   `misc_listing_macros.html` with macros for the stats header, the sort-header link
   matrix (parameterized by `contacts-`/`families-`/... prefix), and the shared row
   cells.
2. **`relay-list.html` vs `contact-relay-list.html` (~200 overlapping lines):** extract
   shared row-cell macros (status circle, nickname/family links, AS, country, platform,
   flags, first-seen); keep contact-specific columns local. Note the intentional
   differences first (first-seen shows date vs time-ago; measured shows text vs icons)
   so the macro parameterizes them rather than silently normalizing.
3. **Thin detail wrappers** (`as.html`, `flag.html`, `platform.html`,
   `first_seen.html` — 10 lines each): acceptable to keep, but move the inline country
   summary in `country.html` into the existing `detail_summary` macro (add an optional
   parameter for the RouteFluxMap link).
4. Unify the operator-link markup duplicated between `macros.html` and
   `aroi_macros.html` into one macro.

**Risk:** medium-high — templates are the output; the comparison tool is the safety
net. Do one template family per commit and demand a noise-floor diff each time.
**Diff:** must be noise floor (byte-identical HTML is the acceptance criterion).

---

## Phase 9 — `page_context.py` and `file_io_utils.py` de-layering

1. `page_context.py`: production uses three convenience functions; delete
   `create_template_context_builder`, `create_standard_contexts`, and the unused
   `StandardTemplateContexts.get_detail_page_context(page_data)` variant; flatten
   `TemplateContextBuilder` into the functions.
2. `file_io_utils.py`: keep `CacheManager`, `TimestampManager`, `StateManager`; delete
   `BulkFileOperations`, `TestFileHelper`, `create_unified_file_manager`,
   `safe_file_operation`, `safe_json_operation` (zero production imports).
3. `page_writer.get_detail_page_context(relay_set, ...)`: drop the ignored `relay_set`
   parameter.

**Risk:** low. **Diff:** noise floor.

---

## Ordering and acceptance

| Phase | Prereq | Acceptance |
|-------|--------|------------|
| 1 escaping | bug-plan Phase 1 merged | noise-floor diff, pytest green |
| 2 error layer | new error-path unit tests written first | noise-floor diff |
| 3 API registry | Phase 2 | noise-floor diff |
| 4 progress | — | no HTML diff; progress format unchanged |
| 5 Relays facade | — | noise-floor diff per batch; parallel rendering verified |
| 6 page writer | Phase 5 | steps 1–2 noise floor; step 3 authorities page reviewed |
| 7 utils merge | — | noise-floor diff per module family |
| 8 templates | Phase 1 | noise-floor diff per template family |
| 9 de-layering | — | noise-floor diff |

Each phase is one or more commits, each commit individually verified with the full
baseline/after/compare cycle. Never batch two phases into one diff review.
