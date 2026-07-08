# Plan 2: Lines-of-Code Reduction Plan

Scope: delete verified dead code and merge verbatim duplication with **zero behavior
change**. Structural refactors are in the simplification plan; behavior changes in the
bug fix plan. Current size: ~23.3k lines of production Python (`allium/` + 
`compare_outputs.py`), ~8.2k lines of templates, ~22.2k lines of tests.

Target: **~900–1,300 production Python lines** plus **~500–700 template lines**
removed, in strictly mechanical, individually-verified steps.

## Workflow (applies to every batch)

```bash
# 1. Baseline BEFORE (full APIs)
python3 allium/allium.py --out allium/www_baseline --apis all --progress

# 2. Delete one batch

# 3. Regenerate AFTER
python3 allium/allium.py --out allium/www_after --apis all --progress

# 4. Compare all ~28k output files
python3 compare_outputs.py --quiet

# 5. Tests + lint
pytest
flake8 . --select=E9,F63,F7,F82 --show-source
```

Verified: full run ≈ 3.5 min / ~7 GB RSS; back-to-back runs have a noise floor of ~25
content-diff files (relay uptime ticking, root timestamps). **Every batch in this plan
must diff at the noise floor.** Dead-code deletion that changes output was not dead —
revert and investigate.

Additional gate for every deletion: `rg -n "<symbol>" allium/ tests/` must show only the
definition (or definition + tests, in which case delete/update the tests in the same
commit).

---

## Batch 1 — Dead functions and classes (zero callers, verified by grep)

| Symbol | File | ~Lines |
|--------|------|--------|
| `handle_worker_errors` decorator (never applied) | `error_handlers.py` | 35 |
| `TemplateEscapingHelpers` class + `create_template_helpers` | `html_escape_utils.py` | 70 |
| `escape_relay_field`, unused `HTMLEscaper.escape_with_*` methods | `html_escape_utils.py` | 20 |
| Dead `first_seen_date` write (mislabeled "unescape") | `html_escape_utils.py` | 1 |
| `StatisticalUtils.calculate_z_score`, `classify_by_z_score`, `calculate_confidence_intervals` | `statistical_utils.py` | 90 |
| Module-level wrappers `calculate_percentile`, `calculate_statistical_outliers` | `statistical_utils.py` | 7 |
| `calculate_network_cv_statistics` (never wired; no caller passes its output) | `bandwidth_utils.py` | 21 |
| `normalize_contact_info` | `aroileaders.py` | 13 |
| `assign_rarity_tier` (superseded by `assign_as_rarity_tier`), `is_eu_geographic`, `get_geographic_regions_for_analysis`, `count_frontier_countries_weighted_with_existing_data` | `country_utils.py` | 50 |
| `format_percentage`, `format_percentage_or_na` (thin aliases of `format_percentage_from_fraction`) | `string_utils.py` | 28 |
| Legacy `log_step_progress`, `log_progress_with_step_increment`, `ProgressLogger.create_child_logger`, `update_from_other_logger` | `progress_logger.py` | 50 |
| `create_template_context_builder`, `create_standard_contexts`, unused `StandardTemplateContexts.get_detail_page_context(page_data)` variant | `page_context.py` | 48 |
| `Relays._write_timestamp`, `Relays.create_output_dir` | `relays.py` | 16 |
| `Coordinator.get_collector_data` (tests-only), `self.workers = {}` | `coordinator.py` | 7 |
| `normalize_uptime_value` (inlined at its only production call site) | `uptime_utils.py` | 12 |

Subtotal ≈ **470 lines**. Where a symbol is exercised only by tests, delete the test in
the same commit (it tests nothing the product uses).

---

## Batch 2 — Unreachable branches

| Item | File | ~Lines |
|------|------|--------|
| Contact-specific logic in the generic sequential `write_pages_by_key` loop — unreachable because `if k == "contact": return` routes contacts to dedicated renderers first | `page_writer.py` | 130 |
| Contact vanity-URL block in `write_pages_parallel` — contacts never reach this function | `page_writer.py` | 15 |
| `network_position_display` assigned but never passed to the template | `page_writer.py` | 1 |

Subtotal ≈ **145 lines**. This is the highest-value single deletion; verify with a full
diff **and** confirm contact pages and vanity URLs are still generated (spot-check
`allium/www_after/contact/<hash>/index.html` count matches baseline).

---

## Batch 3 — Dead pipeline plumbing

| Item | File | ~Lines |
|------|------|--------|
| `fetch_consensus_health` (not in `API_WORKER_REGISTRY`; production never calls it) | `workers.py` | 72 |
| `fetch_collector_data` legacy wrapper | `workers.py` | 6 |
| `get_consensus_health_data` + `consensus_health_data` attach + reader stub | `coordinator.py`, `relays.py` | 40 |
| `_state_manager` global (workers use `_save_state`/`_load_state` directly) | `workers.py` | 1 |
| `BulkFileOperations`, `TestFileHelper`, `create_unified_file_manager`, `safe_file_operation`, `safe_json_operation` | `file_io_utils.py` | 150 |

Subtotal ≈ **270 lines**. Integration tests that call `fetch_consensus_health` directly
must be deleted or repointed in the same commit.

---

## Batch 4 — Unused imports and constants

`flake8 --select=F401` plus the review found: `sys`, `Path`,
`ThreadPoolExecutor`/`FuturesTimeoutError` (`workers.py`); `BandwidthFormatter`,
`get_divisor_for_unit`, module-level `determine_unit` import (`page_writer.py`);
`os` (`progress.py`, `page_context.py`); `ABS_PATH` (`allium.py`); `hashlib`, `html`,
`count_frontier_countries_weighted_with_existing_data` (`aroileaders.py`); `math`
(`intelligence_engine.py`); `json` (`aroi_validation.py`);
`find_relay_uptime_data`, `calculate_relay_uptime_average` imports (`network_health.py`);
duplicate in-function imports in `operator_analysis.calculate_operator_reliability`;
`handle_calculation_errors`, `get_worker_status` imports (`coordinator.py`).

Run `flake8 . --select=F401,F811,F841` to catch the full set mechanically.

Subtotal ≈ **25–35 lines**. No diff expected at all (imports don't render).

---

## Batch 5 — Verbatim duplication merges (still zero behavior change)

These merge copy-paste duplicates where both copies are demonstrably identical in
behavior; anything with semantic differences stays for the simplification/bug plans.

| Duplication | Files | ~Lines saved |
|-------------|-------|--------------|
| Daily bandwidth aggregation loop (`_calculate_growth_trend` vs `extract_operator_daily_bandwidth_totals`) | `bandwidth_utils.py` | 70 |
| `_format_breakdown_details` builds two identical lists then truncates one | `aroileaders.py` | 4 |
| Per-fetcher `log_wrapper` closure repeated 5× | `workers.py` | 25 |
| `_format_leaderboard_entries` 19-category switchboard → table-driven config | `aroileaders.py` | 150–200 |
| Flag uptime/bandwidth display processor pairs (same skeleton, different field names) | `flag_analysis.py`, `operator_analysis.py` | 160–200 |
| Statistical outlier wrapper duplicated in `uptime_utils` and `statistical_utils` | both | 10 |

Subtotal ≈ **420–510 lines**. The last two rows are the riskiest deletions in this plan:
do each as its own commit, and treat *any* content diff above the noise floor as a
failure (the merged implementation must reproduce byte-identical HTML, including CSS
class names — note `flag_analysis` emits `al-status-*` while `operator_analysis` emits
different class names in places; parameterize, don't normalize).

---

## Batch 6 — Template LOC (optional, shared with simplification plan Phase 8)

| Item | ~Lines saved |
|------|--------------|
| `misc-*.html` shared header/sort-matrix/row macros | 400–450 |
| `relay-list.html` / `contact-relay-list.html` shared row macros | 100–150 |
| Inline country summary → `detail_summary` macro | 25 |

Subtotal ≈ **500–650 template lines**. Byte-identical output required (whitespace
included — Jinja `trim_blocks`/`lstrip_blocks` are on, but macro extraction can still
shift whitespace; the comparison tool will catch it).

---

## Non-goals

- `experiments/` and `docs/` cleanup — not production code; handle separately if wanted.
- Deleting `compare_outputs.py` helpers — it is the verification tool for this plan.
- Test-suite slimming beyond tests of deleted code (~22k test lines have their own
  value; only remove tests whose subject is deleted).
- Anything requiring judgment about intended behavior — that belongs to the bug plan.

## Execution order and accounting

1. Batch 4 (imports) — trivial, instant, zero diff.
2. Batch 1 (dead symbols) — grep-gated, one commit per module.
3. Batch 2 (unreachable branches) — one commit, careful diff + page-count check.
4. Batch 3 (dead plumbing) — one commit, update tests.
5. Batch 5 (duplication merges) — one commit per row, strict byte-identical gate.
6. Batch 6 (templates) — one commit per template family.

Running total if all batches land: **~1,330–1,530 Python lines** (~6% of production
Python) **+ ~500–650 template lines** (~7% of templates), all with noise-floor diffs.
Each commit message should state the batch, the symbols removed, and the compare result
(`Content diffs: N (noise floor)`).
