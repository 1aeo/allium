# Plan 3: Bug Fix Plan

Scope: fix verified and suspected bugs found during a full-codebase review. Every phase
follows the output comparison workflow so each fix's HTML impact is observed and reviewed,
not guessed.

## Workflow (applies to every phase)

```bash
# 1. Generate baseline BEFORE the change (full APIs)
python3 allium/allium.py --out allium/www_baseline --apis all --progress

# 2. Apply the fix(es) for one phase

# 3. Regenerate AFTER the change (full APIs, same command)
python3 allium/allium.py --out allium/www_after --apis all --progress

# 4. Diff every generated file (~28k files, ~10s)
python3 compare_outputs.py            # exit 0 = clean, 1 = diffs to review
python3 compare_outputs.py --quiet    # summary only

# 5. Run the test suite
pytest
flake8 . --select=E9,F63,F7,F82 --show-source
```

Environment notes (verified in this repo):

- A full `--apis all` run completes in ~3.5 min and needs ~7 GB RSS.
- Running baseline and after back-to-back reuses warm API caches; the observed noise
  floor is **~25 content-diff files** (relay uptime ticking, root page timestamps).
  Any diff beyond that must be attributable to the fix being verified.
- If onionoo drifts between runs, regenerate the baseline immediately before the
  after-run to keep the cache warm.

Fixes are grouped into phases by risk and by expected HTML impact, so the diff for each
phase isolates one class of change.

---

## Phase 1 — Double-escaped HTML entities (verified, visible to users)

**Bug.** `page_writer.py` enables Jinja2 `autoescape=True`, but `relays.py` /
`html_escape_utils.py` still pre-escape fields (`contact_escaped`,
`nickname_escaped`, `as_name_escaped`, `platform_escaped`, `flags_escaped`,
`first_seen_date_escaped`, `contact_info_escaped` in `aroileaders.py`, …) and templates
render them without `|safe`. Autoescape escapes them a second time.

**Verified evidence.** Generated output contains double-escaped entities rendered as
literal text in the browser (e.g. `&amp;lt;admin AT my-mail dot rocks&amp;gt;` displays
as `&lt;admin AT my-mail dot rocks&gt;`):

- `misc/all.html`: 1,275 occurrences
- `index.html` (AROI leaderboards): 71 occurrences
- `top500.html`: 61 occurrences

**Fix. DECISION: keep escaping logic in Python (Jinja2 is slower); wrap pre-escaped
strings in `markupsafe.Markup`.** Python-side pre-escaping stays — it was introduced
for render performance and template logic should stay minimal. To stop the
double-escaping, have the Python escaping helpers (`html_escape_utils.py`,
`contact_info_escaped` in `aroileaders.py`, and any other `*_escaped` producers) return
`markupsafe.Markup(html.escape(value))` instead of a plain `str`. Autoescape treats
`Markup` as already-safe and will not re-escape it, while remaining on as the safety
net for every raw field. Rules:

- Only wrap strings in `Markup` at the point they pass through `html.escape()` (or are
  built exclusively from already-escaped parts, like `_flags_html`). Never wrap raw
  onionoo data.
- Do NOT sprinkle `|safe` in templates — `Markup` at the Python source centralizes the
  safety decision at the same place the escaping happens.
- `markupsafe` is a hard dependency of Jinja2, so this adds no new dependency.

**Expected diff.** Large but mechanical: affected pages change `&amp;amp;` → `&amp;`,
`&amp;lt;` → `&lt;`, etc. Verify by grepping the after-output:
`rg -c "&amp;amp;|&amp;lt;" allium/www_after/misc/all.html` should return 0 (or only
legitimately double-escaped operator strings that literally contain `&amp;`).
Spot-check that single escaping is still present (no raw `<script>` in output):
`rg -l "<script" allium/www_after/misc/all.html` should only match the intentional
page scripts.

**Files.** `allium/lib/html_escape_utils.py`, `allium/lib/relays.py`,
`allium/lib/aroileaders.py`, templates using `*_escaped` fields
(`relay-list.html`, `contact-relay-list.html`, `aroi_macros.html`).

---

## Phase 2 — HTTP 304/error cache fallback never finds the cache (verified, no HTML diff expected)

**Bug.** `error_handlers.handle_http_errors(api_name, cache_loader, ...)` is invoked with
display names — `"onionoo details"`, `"onionoo historical bandwidth"`, `"AROI validation"`,
`"Exit DNS Health"` (`workers.py` lines 792–927). On HTTP 304 and on the generic
exception fallback it calls `cache_loader(api_name)`, and `CacheManager.save_cache/load_cache`
build filenames as `f"{cache_key}.json"`. The cache is written under the config
`api_name` (`onionoo_details.json`), so the decorator looks for `onionoo details.json`,
which never exists. The same wrong key is passed to `_mark_ready`/`_mark_stale`, so worker
state entries are also keyed inconsistently with the coordinator's registry.

**Fix.** Pass the machine key and display name separately, e.g.
`@handle_http_errors(cache_key="onionoo_details", display_name="onionoo details", ...)`,
and use `cache_key` for `cache_loader`/`mark_ready`/`mark_stale`, `display_name` for log
messages only.

**Test.** Unit test: mock a 304 `HTTPError` from `_fetch_with_cache_fallback`, pre-seed
`onionoo_details.json` cache, assert cached data is returned and worker status is keyed
`onionoo_details`. The full-run diff should show **zero** content diffs beyond the noise
floor (this path only triggers on 304/error).

**Files.** `allium/lib/error_handlers.py`, `allium/lib/workers.py`,
`tests/unit/workers/`.

---

## Phase 3 — Contact page downtime alerts double/triple-count dual-role relays (HTML diff expected)

**Bug.** `operator_analysis.py` (~lines 1451–1463): an offline relay with both `Guard`
and `Exit` flags increments `guard`, `exit`, **and** `middle` buckets. `contact.html`
(line ~328) sums the three buckets into `total_offline`, so one offline Guard+Exit relay
counts as 3. Per-role offline bandwidth percentages can also exceed 100%.

**Fix. DECISION: exclusive buckets with the codebase's priority order, all math in
Python.** Two parts:

1. Classify each offline relay into exactly one bucket using the same priority rule
   used elsewhere (`contact_sorting.py` role_rank and `categorization.py` role
   counting both use **Exit > Guard > Middle**): `if 'Exit' in flags → exit;
   elif 'Guard' in flags → guard; else → middle`. This also aligns the per-role
   offline bandwidth sums with the `guard_bandwidth`/`exit_bandwidth`/
   `middle_bandwidth` denominators, which `categorization.py` already computes with
   the same exclusive rule — so per-role percentages can no longer exceed 100%.
2. Compute `total_offline` in Python (`len(offline_relays)`) and put it in
   `downtime_alerts`; remove the `{% set total_offline = ... %}` arithmetic from
   `contact.html`. Jinja2 is slower than Python — templates should render
   precomputed values, not do math (this is the established pattern:
   `_preprocess_template_data`, `preformat_network_health_template_strings`).

**Expected diff.** Contact pages of operators that currently have offline dual-role
relays; verify a sampled contact page shows the corrected count.

**Files.** `allium/lib/operator_analysis.py`, `allium/templates/contact.html`.

---

## Phase 4 — Reliability leaderboard drops 0% uptime relays from the average (HTML diff expected)

**Bug.** `aroileaders.py` line ~250: `if uptime_pct > 0.0:` excludes relays with exactly
0% uptime from the operator average. Nine relays at 99% plus one at 0% scores ~99%
instead of ~89.1%, inflating "Reliability Masters"/"Legacy Titans" rankings.

**Fix.** Include explicit 0.0 values when the relay has uptime data for the period;
only skip relays with **missing** data. Distinguish "no data" (`None` /
missing key) from "0% uptime" when reading `uptime_percentages`.

**Expected diff.** Reliability leaderboard sections of `index.html` /
`misc/aroi-leaderboards.html`, and contact pages showing reliability scores.

**Files.** `allium/lib/aroileaders.py` (and the analogous logic in
`operator_analysis.calculate_operator_reliability` if it shares the pattern),
`tests/unit/aroi/`.

---

## Phase 5 — Inconsistent v3 migration percentage denominators (HTML diff expected)

**Bug.** `aroi_validation.py` (~line 1806) computes `v3_relay_percentage` as
`v3 / (v2 + v3)` (AROI-declaring relays only) while `aroileaders.py` (~line 965) uses
`v3 / total_relays`. The same operator shows different percentages on contact pages vs
leaderboards. It is self-contradictory within a single sentence on the contact page
(`contact-relay-list.html` line ~482): "**50%** of this operator's relays already
declare ciissversion:3 (**1 of 50**)" — the percentage uses `v2+v3` while the
parenthetical uses `total_relays`. `v3_tier` and `is_v3_adopter` already use
`total_relays` everywhere.

**Options considered.**

- A — standardize on `total_relays`: matches `classify_v3_tier`, `is_v3_adopter`, and
  the existing "(N of M)" template copy, but the mixed-migration pill would undersell
  migration progress for operators where only a few relays declare AROI.
- B — standardize on `v2 + v3` ("migration progress among AROI-declaring relays"):
  would misstate the leaderboard "share of relays on v3" columns.
- **C — keep both semantics under two distinct field names** (chosen): most precise;
  each surface gets the number that matches its copy.

**DECISION: Option C.** Replace the ambiguous `v3_relay_percentage` with two
explicitly-named fields, both computed in Python (`aroi_validation.py`), never in
templates:

- `v3_pct_of_total = v3_relay_count / total_relays * 100` — used by leaderboard
  columns, `v3_tier`, `is_v3_adopter`, and the contact-page sentence
  "X% of this operator's relays already declare ciissversion:3 (N of TOTAL)"
  (fixing the self-contradiction, since the parenthetical already uses totals).
- `v3_migration_progress_pct = v3_relay_count / (v2_relay_count + v3_relay_count) * 100`
  — used by the "🔁 X% v3" mixed-migration pill (only shown when both v2 and v3
  exist), with tooltip copy updated to say "of AROI-declaring relays".

Deleting the old name (rather than keeping it as an alias) forces every consumer —
templates, search index, Prometheus — to pick the right semantics explicitly.

**Files.** `allium/lib/aroi_validation.py`, `allium/lib/aroileaders.py`,
`allium/lib/page_writer.py` (`aroi_v3_pct`), templates `contact-relay-list.html`,
`macros.html`; grep for `v3_relay_percentage` / `v3_relay_pct_str` to catch all
consumers. Verify with the diff on contact pages and leaderboard v3 columns;
cross-check one mixed-migration operator by hand on both surfaces.

---

## Phase 6 — Timezone and determinism bugs (small HTML diffs possible)

1. **Veteran score uses naive local time.** `aroileaders.py` (~lines 795–812) uses
   `datetime.now()` (naive, host-local) and `strptime` on onionoo's UTC timestamps;
   every other consumer uses UTC-aware helpers (`time_utils.parse_onionoo_timestamp`).
   On a non-UTC host, `veteran_days` drifts by up to ±1 day (more around DST), making
   output non-reproducible across machines.
   Options: (A, chosen) `datetime.now(timezone.utc)` + `parse_onionoo_timestamp()` —
   consistent with the rest of the codebase; (B) `datetime.utcnow()` — minimal but
   deprecated in Python 3.12; (C) leave as-is and rely on UTC hosts — silently
   re-breaks on any non-UTC machine.
   **DECISION: Option A.** On a UTC host the diff must be noise-floor only.
2. **Leaderboard ties are nondeterministic.** `_top_n` (`aroileaders.py` line 98) sorts
   by a single metric; ties currently break by dict insertion order. (The *operator
   key* is the dict key of `aroi_operators` — the operator's AROI domain when one is
   declared, otherwise the derived incomplete-AROI display name /
   `contact_<hash-prefix>` from `_incomplete_aroi_display_name`.)
   **DECISION:** break ties by relay count so the tied operator with more relays wins,
   then by operator key only as a final determinism guarantee:
   `key=lambda x: (-x[1][metric], -x[1]['total_relays'], x[0])`. The operator-key
   tertiary never affects who "wins" a meaningful tie — it only pins the order when
   metric AND relay count are both identical, so output is byte-stable across runs.
3. **`total_steps` comment is stale.** `allium.py` line 296 says "59 total steps" but the
   computed value is 61 (4+22+35) and the run logs `[61/61]` (verified).
   **DECISION: derive the count dynamically** so it stays correct going forward:
   compute coordinator steps from the enabled API worker registry (per-API step count ×
   number of enabled APIs + fixed data-processing steps) and page-generation steps from
   `site_generator` page definitions (`STANDALONE_PAGES`, `MISC_SORTED_PAGE_TYPES`,
   detail-page categories, search index, Prometheus) instead of hard-coded literals.
   Expose the derivation next to the registries it counts, so adding an API or page
   type updates the total automatically. No HTML impact (stdout progress only).

**Files.** `allium/lib/aroileaders.py`, `allium/allium.py`.

---

## Phase 7 — Template correctness (HTML diff expected, cosmetic)

1. **Broken nav highlighting.** `flag.html` and `first_seen.html` call
   `navigation('misc', ...)` but the macro has no `'misc'` branch — nothing highlights.
   `relay-info.html` uses `navigation('all', ...)`, wrongly highlighting "All Relays"
   on relay pages. Fix: pass a valid section or none.
2. **Country breadcrumb shows ISO code.** `page_context.get_detail_context()` puts the
   raw sorted key (e.g. `US`) into `country_name`; `country.html` derives the full name
   separately. Fix: resolve the display name in `get_detail_context`.
3. **Sort variants with no visible column.** `site_generator.py` generates
   `by-unique-contact-count` / `by-unique-family-count` pages for all five misc types,
   but `misc-contacts.html` and `misc-families.html` have no such columns — the pages
   exist with no visual indication of the sort. Fix: either add the columns or stop
   generating those variants for those two types (note: removing variants deletes
   4 output files — the comparison report will show them under "Only in baseline",
   which is the expected signal).
4. **`platform.html` description doesn't escape `value`** while the title does
   (autoescape actually covers this — verify, then align the template for consistency).

**Files.** `allium/templates/macros.html`, `flag.html`, `first_seen.html`,
`relay-info.html`, `platform.html`, `allium/lib/page_context.py`,
`allium/lib/site_generator.py`.

---

## Phase 8 — Data/display correctness in diagnostics (HTML diff expected, small)

1. **`burst-limit` formatted as a rate.** Per proposal 328 / dir-spec, onionoo's
   `overload_ratelimits.rate-limit`/`burst-limit` are the raw torrc `BandwidthRate`
   (bytes **per second**) and `BandwidthBurst` (token-bucket size in **bytes** — a
   quantity, not a rate). `relay_diagnostics.py` (~line 606) and `relay-info.html`
   (~line 980) render burst with `/s` units, so a 1 GB bucket shows as "1.07 GB/s".
   Options: (A, chosen) format burst as a data volume, no `/s` — spec-correct, and the
   diagnostics page should teach the correct semantics; (B) keep rate-style display to
   match operators' torrc mental model — status quo; (C) raw bytes — unambiguous but
   inconsistent with site formatting.
   **DECISION: Option A.** Small diff confined to relay pages with overload data plus
   the "Rate Limit Configuration" issue text.
2. **Guard bandwidth message ignores `--bits`.** `relay_diagnostics.py` line ~276
   hardcodes `f"{observed_bandwidth / 1_000_000:.1f} MB/s"`. Fix: use the shared
   formatter with `use_bits`.
3. **IPv6 directory authority parsing.** `page_writer.py` (~lines 649–655) splits
   `or_addresses[0]` on `:`, which breaks `[2001:db8::1]:9001` (yields `[2001`), and
   `dir_address.split(':')[-1]` has the same flaw. **Latent today:** onionoo lists each
   authority's IPv4 address first and `dir_address` is IPv4, so current output is
   correct; it breaks only if an authority ever publishes IPv6-first, at which point
   the latency probe silently targets a garbage endpoint and reports the authority down.
   Options: (A, chosen) bracket-aware parsing via `ip_utils.safe_parse_ip_address`,
   preferring the first IPv4 entry for the probe (the monitor's TCP check is only
   exercised over IPv4); (B) IPv4-filter only; (C) leave as-is.
   **DECISION: Option A** (which subsumes B's explicit IPv4 preference). Zero expected
   output change today — the diff must be noise-floor only.
4. **Stable-flag eligibility defaults to eligible.** `consensus/collector_fetcher.py`
   (~line 1102): when an authority publishes no `stable-mtbf` threshold, every relay is
   marked Stable-eligible. Fix: fall back to the documented dir-spec OR-condition
   (`flag_thresholds.check_stable_eligibility`) instead of `True`.

---

## Phase 9 — Latent bugs (mostly no HTML diff expected; fix + unit test)

1. **Rare-country loop iterates category names.** `country_utils.py` lines 574–592
   iterate `GEOPOLITICAL_CLASSIFICATIONS.keys()` (`'conflict_zones'`, `'authoritarian'`, …)
   instead of country codes, adding those strings to the rare-country set. Currently
   masked because both consumers filter to 2-letter codes; still wrong.
   **DECISION: iterate the union of the classification sets** — i.e.
   `set().union(*GEOPOLITICAL_CLASSIFICATIONS.values())` — so zero-relay but
   geopolitically significant countries are scored as intended (the block's original
   purpose). Note this may legitimately add real country codes to the rare set that
   were previously missing; review the resulting diff on AROI rare-country leaderboards
   and network-health rare-country metrics rather than expecting a noise-floor result.
2. **`first_seen_date` re-escapes instead of unescaping.** `html_escape_utils.py`
   line 297: comment says "Unescape" but code does `.replace('&', '&amp;')`. Field is
   unused in templates — remove it (also covered by Phase 1 rework).
3. **Non-atomic state/cache writes.** `workers._save_state` and
   `file_io_utils.write_json_file` write JSON in place; a crash mid-write corrupts
   state/cache. Fix: write to temp file + `os.replace`.
4. **`_is_retryable_error` retries all `OSError`s** (`workers.py` ~line 511), including
   `ENOSPC`/`EACCES`. Fix: restrict to network-related errno values.
5. **Fragile exception handler in `fetch_collector_consensus_data`** (`workers.py`
   ~lines 999–1065): initialize `cached_data`/`timeout_seconds` before the `try`.

---

## Verification matrix

| Phase | Expected compare_outputs result | Extra checks |
|-------|--------------------------------|--------------|
| 1 | Many diffs, all entity-decoding only | grep for `&amp;amp;`/`&amp;lt;` count → 0; XSS spot-check |
| 2 | Noise floor only | new unit test for 304 fallback |
| 3 | Contact pages with offline dual-role relays | sample page inspection |
| 4 | Leaderboard + contact reliability sections | recompute one operator by hand |
| 5 | Contact pill/copy + leaderboard v3 columns (two named fields) | one mixed-migration operator cross-checked on both surfaces |
| 6 | Ties may reorder once (relay-count tiebreak), then stable | re-run twice; second diff must be noise-floor only |
| 7 | Nav/breadcrumb markup diffs; 4 files removed if variants dropped | — |
| 8 | Relay pages with burst-limit/overload data; authorities page expected unchanged (IPv6 fix is latent) | — |
| 9 | Noise floor except item 1 (rare-country fix may add zero-relay countries — review AROI/network-health rare-country surfaces) | unit tests per fix |

After each phase: `pytest` must pass, then commit that phase separately so each diff
review maps to one class of change.
