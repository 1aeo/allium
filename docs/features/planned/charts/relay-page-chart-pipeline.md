# Relay-page chart pipeline

**Audience**: Contributors implementing charts on `relay-info.html`
**Status**: Locked architecture. First chart: `relay_bandwidth_1m` (style 5 / option C).
**Encoding spec**: [`relay-page-charts.md`](relay-page-charts.md)
**Frozen bands**: [`data/role_ratio_bands.json`](data/role_ratio_bands.json)

This document is the build-time plan. It does **not** re-open identity,
chrome, C subtitles, or the always-on top Investigate band. Those are
locked in the encoding spec. This file answers: how do we draw that one
PNG on every relay page without turning the ~5 minute HTML generate into
a 25 minute matplotlib generate, and how does the next chart plug in.

---

## Decision (do this)

Ship charts as a **decoupled process-pool pass after HTML**, with a
**content-hash cache** and a **chart registry**.

| Piece | Choice |
|-------|--------|
| When | After `generate_site()` returns. Not inside Jinja. Not inside `write_relay_info()`. |
| How | `multiprocessing` **spawn** pool, default `min(4, cpu_count)`. Slim picklable jobs. |
| What | Registry entry → renderer → PNG. First id: `relay_bandwidth_1m`. |
| Cache | SHA-256 of chart version + the fields that actually change the figure. Sidecar + PNG under `{output}/.chart-cache/`. |
| Publish | After HTML, hardlink/copy cache PNG to `www/relay/<fp>/bandwidth-1m.png`. |
| Deps | matplotlib is a **build extra** (`config/requirements-charts.txt`). Core generate stays Jinja2-only. |
| CLI | `--charts {off,auto,on}` and `--no-charts`. **Default stays `off`.** `auto` is an explicit choice (do not flip the argparse default to `auto`). Ramp with `--charts-limit N` and repeatable `--fingerprint FP`. |
| HTML | History `<img>` only when the chart pass will actually run **and** that fingerprint is in the sliced 1M set. Default-off generate must not emit ~7k broken images. |

The 5-minute number stays the HTML number. Charts are a second, cacheable
bill. Same-day rebuilds that only tick votes / uptime / `last_seen` must
not redraw ~7k–11k figures.

---

## What the generate path actually does today

Read this before changing anything. Several “obvious” designs die on
these facts.

### Pipeline shape

```
allium.py
  └─ Coordinator.fetch_all_apis_threaded()     threads, I/O
        details + uptime + bandwidth + AROI + …
  └─ Relays.__init__ + enrich_with_api_data()  sequential CPU
  └─ generate_site()                           Page Generation
        standalone pages
        misc sorted pages
        write_pages_by_key()  → fork Pool (--workers, default max(4, cpu))
              family / contact / as / country / flag / platform / first_seen
        write_relay_info()    → sequential Jinja, ~7k files
        _sync_static_files()  → copy allium/static → www/static
        search index, prometheus, SEO
```

- API fetch is **threads**. Safe for I/O. Useless for matplotlib
  (GIL + not thread-safe).
- Group pages are **fork workers** (`page_writer.py`). `--workers`
  defaults to `max(4, os.cpu_count() or 4)` — often 8–16. Those workers
  render Jinja from a forked `Relays` object. They must stay Jinja-only.
- **Relay pages are sequential.** `write_relay_info()` loops
  `relay_set.json["relays"]`, renders `relay-info.html`, writes
  `www/relay/<fingerprint>/index.html`. No pool. This is already a
  large slice of the 5-minute run. Putting matplotlib here is how you
  turn 5 minutes into 30.
- `--apis all` is the ~2.4 GB / ~5 minute path (~21,700 HTML pages).
  `--apis details` skips `/bandwidth` and `/uptime` (~400 MB, 1–2 min).
  Charts that need `/bandwidth` cannot run in details-only mode.
- Progress totals are derived from worker + page-name registries
  (`allium.py`). Do **not** add chart steps to that total until the
  renderer is on by default. Chart logs use
  `progress_logger.log_without_increment` so a default-off run has the
  same step count as today.

### Bandwidth data is already in memory — then thrown away

`fetch_onionoo_bandwidth()` runs in a worker thread. Default cache is
**12 hours** (`--bandwidth-cache-hours`, `BANDWIDTH_CACHE_MAX_AGE_HOURS`).
A generate inside that window reuses the same `/bandwidth` JSON.

`Coordinator.create_relay_set()` keeps the raw document on
`relay_set.bandwidth_data` and then
`Relays._reprocess_bandwidth_data()` →
`process_all_bandwidth_data_consolidated()`. That function:

- reads `read_history` / `write_history`
- stores **averages** (`6_months` / `1_year` / `5_years` only) and
  **totals** on each relay
- merges `overload_ratelimits` / `overload_fd_exhausted`
- **does not keep `1_month` values, `first`, `interval`, or `factor`**
  on the relay object

Charts must read `relay_set.bandwidth_data` (or a one-time
`build_bandwidth_map()` over it). Do **not** attach 1M arrays to every
relay dict for Jinja. That would grow the object the HTML path already
walks, and it is unnecessary: the raw document is still on the
`Relays` instance after enrichment.

`1_month` write/read is daily buckets (`interval` 86400). Intra-day
rebuilds with a warm bandwidth cache see the **same series**. That is
the cache’s main hit. The next Onionoo day will miss, and should.

### `write_relay_info()` deletes the relay tree

```python
output_path = os.path.join(relay_set.output_dir, "relay")
if os.path.exists(output_path):
    rmtree(output_path)
os.makedirs(output_path)
```

Every HTML generate wipes `www/relay/**`. A PNG written next to
`index.html` **before** this function, or left from yesterday, is gone.

`_sync_static_files()` copies `allium/static/` → `www/static/` and does
**not** prune extras. Files under `www/static/charts/` would survive
static sync, but they are the wrong durable cache if we also want
relative `bandwidth-1m.png` next to the relay page.

**Layout that survives this:**

| Role | Path |
|------|------|
| Durable cache | `{output}/.chart-cache/{chart_id}/{fingerprint}.png` + `.json` sidecar |
| Published file | `{output}/relay/{fingerprint}/bandwidth-1m.png` (after HTML) |
| Later `<img>` | `src="bandwidth-1m.png"` (same directory as `index.html`) |

Cache hit = hardlink (fallback copy) from `.chart-cache` into the
freshly recreated relay directory. Milliseconds. No matplotlib.

`.chart-cache/` is gitignored. `www/` is already gitignored.

### How many figures

| Set | Typical count |
|-----|----------------|
| Relay HTML pages | ~7,000 (`docs/reference/output-structure.md`); encoding doc also cites ~11k |
| Total HTML pages | ~21,700 |
| First chart | one `relay_bandwidth_1m` PNG per relay that has a 1M write/read graph |
| Thin / missing history | skip PNG; no “two dots”; later template omits `<img>` |

Budget the cold pass against ~7k–11k figures, not 22k. The 22k number
is HTML.

### Identity and advertised already exist on details

- `nickname`, `fingerprint`, `flags`, `advertised_bandwidth`,
  `last_restarted`, `overload_general_timestamp`, `contact` — details.
- Chart identity operator is the contact `url:` host (mockup
  `operator_from_contact`). **Not** `relay["aroi_domain"]`. That field
  is only set for a complete AROI triple. Digitalcourage-style `url:`
  without full AROI still belongs on the figure.
- Overload cue uses `current_overload_status()` in
  `stability_utils.py` with **`relays_published` as the clock**, not
  wall time. Same as the mockups.
- Role is `Exit+Guard` / `Exit` / `Guard` / `Middle` from `flags`
  (`role_of` in the mockup script).

---

## Locked visual (renderer contract, not this skeleton)

`render_relay_bandwidth_1m(...)` must match the shipped mockups:

- Identity **above** Throughput, 13 pt bold, AROI/`url:` host when
  present, real gap, no overlap, not repeated on the write/read strip
- Dual line + write/read strip, legends at the **top**, 8 pt
- C subtitles: spiked / dropped with dates when non-common; inside /
  outside the band; **empty on all-clear**
- Always-on top Investigate red band
- Light theme, Okabe–Ito, `trim=True`

Do **not** port
`docs/features/planned/charts/generate_relay_page_chart_variations.py`
(~5.6k lines, every rejected encoding) into `allium/lib/`. Extract a
slim module. The mockup script can call that module later.

---

## Chart registry

One spec per chart type. Adding a chart is a new entry + a renderer +
a later template slot. No new CLI flags per chart.

```
ChartSpec
  chart_id              relay_bandwidth_1m
  page_slot             relay#bandwidth
  onionoo_inputs        (details, bandwidth)
  period                1_month
  output_path_pattern   relay/{fingerprint}/bandwidth-1m.png
  cache_subdir          relay_bandwidth_1m
  renderer_module       allium.lib.charts.bandwidth
  renderer_name         render_relay_bandwidth_1m
  renderer_version      1          # bump when pixels change
  locked_style          style5_option_c
  enabled               True
```

First — and until the 1M renderer is real, only — registered id:
`relay_bandwidth_1m`.

Later ids (do not implement now):

| id | page_slot | inputs |
|----|-----------|--------|
| `relay_bandwidth_6m` / `_1y` / `_5y` | `relay#bandwidth` sparks | details + bandwidth |
| `relay_uptime_1m` | `relay#uptime` | details + uptime |
| `relay_flags_*` | `relay#flags` | details + uptime |
| `contact_bandwidth_overlay` | `contact#…` | details + bandwidth |

The pass iterates `enabled_charts()`. Shared: cache, pool, output
layout, progress.

Module: `allium/lib/charts/registry.py`.

---

## Decouple from the HTML hot path

`relay-info.html` must not import matplotlib, call a renderer, or wait
on PNG bytes.

**This turn: no template change.** The 5-minute generate and
`compare_outputs.py` stay untouched.

**Next turn (renderer + HTML):** after Network Participation, before
`#bandwidth`’s closing `</section>` (locked option C). The live
template already closes `#bandwidth` there; “Bandwidth Values
Explained” currently lives under the flags block, not inside
`#bandwidth`. Insert:

```html
<h5 class="subsection-header">History</h5>
<img src="bandwidth-1m.png"
     alt="Throughput and write/read, last 30 days"
     width="…" height="…">
```

Emit the History `<img>` only when charts will actually run **and**
that fingerprint has a 1M graph (and survives `--charts-limit` /
`--fingerprint`). That is an in-memory set set **before** Jinja
(`charts_enabled` + `bandwidth_chart_fps`), not a 7k-file `stat`.
Default-off generate must not emit ~7k broken images. Do not mark
the set after the chart pass — that would need a second HTML pass.

`page_ctx.path_prefix` for relay pages is `../../`. A same-directory
`bandwidth-1m.png` does not use it.

---

## Chart pass and CLI

Hook in `allium.py` **after** `generate_site(...)`:

```
generate_site(RELAY_SET, args, progress_logger)
maybe_run_charts(RELAY_SET, args, progress_logger)
```

### Flags

```
--charts {off,auto,on}     default: off
--charts                   const=on       (bare --charts means on)
--no-charts                store off
--charts-limit N           first N chartable relays (0 = no limit)
--fingerprint FP           repeatable; only these fingerprints
--chart-workers N          default 0 → min(4, cpu_count); hard cap 8
```

**Do not reuse `--workers`.** HTML workers are often 8–16. Sixteen
matplotlib processes on a 2.4 GB `Relays` object is a memory incident.
Chart workers get their own cap (max 8). First real chart run should
be a slice: `--charts on --fingerprint …` or `--charts on --charts-limit N`.

### Mode behavior

| Mode | matplotlib missing | renderer missing | extra + renderer present |
|------|--------------------|------------------|---------------------------|
| `off` (default) | silent return | silent return | silent return |
| `auto` | one line, skip | one line, skip | run pass |
| `on` | one line + how to install extra; HTML still succeeds | one line “renderer not implemented”; HTML still succeeds | run pass |

Do **not** flip the argparse default to `auto`. Operators who
installed the extra still opt in with `--charts auto` or `--charts on`.
A surprise matplotlib pass on an ordinary generate is a footgun.

`--apis details`: no `bandwidth_data` → one line, skip. Do not fail.

### Pass algorithm (when renderer exists)

1. HTML generate has finished. `www/relay/<fp>/index.html` exists.
   `www/relay/` was just rebuilt from scratch.
2. `build_bandwidth_map(relay_set.bandwidth_data)` once.
3. Compute role-median **once** and family-median **once per
   `effective_family`** in the parent. Omit the operator line when
   that family has n&lt;2 chartable members. Workers receive overlay
   blobs only — no contact-group walk, no per-job O(n) pass.
4. For each selected relay with a 1M graph, build the cache payload, hash it.
5. Parent-side skip if sidecar key matches and cache PNG exists.
6. Remaining jobs → spawn pool, `min(4, cpu, 8)` processes
   (``--chart-workers`` hard-capped at 8). Each job is try/except:
   one bad relay must not kill the pool. HTML already succeeded.
7. Progress: `Charts: 1200/8340 rendered, 7100 cache hits (12.4s)`
   via `log_without_increment`. Non-zero failed count is printed on
   the same summary line.

### Concurrency budget

**Default: HTML first, then charts.** Keeps the 5-minute number
honest. Do not overlap matplotlib with the HTML pool.

Measure a cold pass before considering overlap. If we ever overlap,
start charts only after fetch+enrich (data is in memory) on the small
chart pool, and only after `write_relay_info()` has recreated
`www/relay/` — otherwise the publish hardlink lands in a directory
that is about to be `rmtree`’d. That constraint means “overlap” can
only run during search-index / prometheus / SEO, which is the tail.
Not worth it until measured. Stay sequential: HTML, then charts.

Use **spawn**, not fork, for chart workers. HTML already uses fork
because the `Relays` object is huge and Jinja is picklable-by-inheritance.
matplotlib + fork is a known source of deadlocks and corrupted figures.
Jobs are slim dicts; spawn is fine.

Initializer: `matplotlib.use("Agg")` then import pyplot once per
process. Never import matplotlib in the parent HTML process.

---

## Cache key (the 5-minute → not-25-minute lever)

`cache_key(payload) → 64-char sha256 hex`.

Canonical JSON: `sort_keys=True`, `separators=(",", ":")`,
`allow_nan=False`. Lists keep Onionoo order. `null` stays `null`.

### Fields that belong (`relay_bandwidth_1m`)

| Field | Why |
|-------|-----|
| `schema_version` | Payload layout. Currently `2`. |
| `chart_id` | `relay_bandwidth_1m` |
| `renderer_version` | Bump when style 5 drawing changes. |
| `fingerprint` | Path + identity |
| `currently_overloaded` | Derived from `current_overload_status()` at the published clock. **Not** raw `relays_published` — a details tick must not bust every figure. |
| `bandwidth_units` | `bits` / `bytes` — advertised legend text |
| `nickname` | Identity line |
| `operator` | `url:` host or `""` |
| `advertised_bandwidth` | Orange dashed line (bytes/s, as Onionoo) |
| `flags` | Sorted tuple; role is derived, include both `flags` and `role` |
| `role` | `Exit+Guard` / `Exit` / `Guard` / `Middle` |
| `last_restarted` | Vertical line |
| `overload_general_timestamp` | Legend diamond |
| `overload_ratelimits` | `{timestamp, write-count, read-count}` only |
| `overload_fd_exhausted` | `{timestamp}` only |
| `write_1m` | `{first, last, interval, factor, values}` |
| `read_1m` | same |
| `family_overlay` | Aligned daily medians + `n`, or `null` if n&lt;2 |
| `role_overlay` | Aligned daily role medians |
| `bands_frozen_from` | `role_ratio_bands.json` `"frozen_from"` so a census rebuild invalidates |

### Fields that must not be in the key

Vote counts, `last_seen`, `observed_bandwidth` (the advertised line
uses `advertised_bandwidth`), uptime percentages, consensus weight,
AS name, raw contact dump, platform, country, and raw
`relays_published`. Those tick every details refresh and would force
a full redraw. The renderer still gets `relays_published` as the 72h
clock; the key stores only the derived boolean.

### Hit / miss

```
{output}/.chart-cache/relay_bandwidth_1m/<fp>.json
{output}/.chart-cache/relay_bandwidth_1m/<fp>.png
```

Sidecar: `{"key": "<hex>", "chart_id": "...", "fingerprint": "..."}`.

Hit: sidecar `key` equals today’s hash **and** the PNG exists.
Then hardlink/copy to `relay/<fp>/bandwidth-1m.png`.

Miss: render, write both cache files, then publish.

Optional later GC: delete cache files whose fingerprint is no longer
in `details` (relays filtered by `--filter-downtime`). Not required
for v1.

### Why daily rebuilds stay cheap

`/bandwidth` is cached 12 hours. Details refresh more often (votes,
uptime scalars). The key ignores those ticks. A generate that reuses
the bandwidth cache and has the same advertised / flags / nickname /
restart / derived overload boolean / identity **skips matplotlib for
that relay**.

When Onionoo publishes a new daily bucket, `write_1m` / `read_1m`
change → miss → redraw. That is correct.

Overlays are computed from the same bandwidth document. If that
document is unchanged, overlay hashes are unchanged. Include them
anyway so a future “rebuild overlays only” path stays honest.

---

## matplotlib is a build extra

Production rule today: Python 3.8+, Jinja2 only
(`config/requirements.txt`).

```
# config/requirements-charts.txt
matplotlib>=3.5.0
```

matplotlib 3.8 dropped Python 3.8. Operators on 3.8 pin `3.7.x`.
Do not add matplotlib to `requirements.txt` or `requirements-dev.txt`.

There is no `setup.py` / extras today. Document:

```
pip3 install -r config/requirements-charts.txt
```

If packaging grows an extra, it should be `[charts]` pointing at the
same pin. Detect the extra with `importlib.util.find_spec("matplotlib")`,
not a package metadata check.

**Never** `import matplotlib` at module import of
`allium.lib.charts`. The HTML process must not pay that cost.
`find_spec` is enough for the skip decision.

---

## Slim renderer (next implementation turn)

New module, not a copy of the mockup script:

```
allium/lib/charts/
  __init__.py
  registry.py          # this turn
  cache.py             # this turn
  identity.py          # this turn (url: host)
  pipeline.py          # this turn (CLI resolve + skip)
  bandwidth.py         # next: data prep + render_relay_bandwidth_1m
```

`bandwidth.py` responsibilities:

1. Accept already-fetched Onionoo dicts + details fields (no HTTP).
2. Build style-5 figure. Agg backend. `trim=True`.
3. Write PNG. No gallery HTML. No alternate encodings.

Shared pieces to lift from the mockup, not rewrite from memory:
identity placement, C subtitle builder, band legend labels, always-on
top Investigate shelf, Okabe–Ito constants, frozen
`role_ratio_bands.json` (ship a copy under `allium/lib/charts/data/`
or read the planned-docs file until it moves to `allium/data/`).

Parent precomputes overlays; workers do not walk the full bandwidth
list.

---

## Future charts

Adding a chart:

1. Register a `ChartSpec`.
2. Write `render_<id>(job) -> path`.
3. Add a template slot when HTML should show it.
4. Extend `build_*_payload()` / cache fields for that spec.

No `--charts-uptime` flag. No second pool. No second cache root.

Contact-page overlays and network-health charts use the same pass
with a different `page_slot` and `output_path_pattern`. They still
run after HTML.

---

## Rejected approaches

### Matplotlib inside each relay HTML worker

`write_relay_info()` is sequential Jinja. Even if we later
multiprocess it, those workers already hold the full `Relays` object
and are sized by `--workers` (often 8–16). Importing matplotlib and
building a figure per page:

- adds ~100–300 ms+ per relay on the HTML critical path
- is not thread-safe
- fights the GIL if anyone tries threads
- makes the published “2–5 minutes” number a lie

The 5-minute path stays Jinja-only.

### One giant megaplot

A single figure with 7k small-multiples is unreadable on a relay page
and does not cache per fingerprint. Operators need *this* relay’s
month.

### Client-side JS (Chart.js / D3)

Production has no chart JS runtime. Search is a JSON index +
Cloudflare function. Shipping a JS library on ~7k relay pages is a
new runtime dependency, a CSP/size conversation, and a worse offline
story. The site is static. Build-time PNG (or later SVG) is the
product.

### SVG via Jinja as the first bandwidth chart

Faster than matplotlib and extra-free. It is also a large, faithful
port of style 5 (dual axes, clipped triangles, identity gap, two
top legends, C copy, always-on Investigate shelf, trim). Do not
block the locked PNG on that rewrite. SVG remains a later option
for the same registry (another renderer on the same spec, or a
sibling spec). First bandwidth chart is matplotlib PNG.

### In-template “if file exists” I/O

7k `os.path.exists` calls during Jinja are avoidable. If the HTML PR
needs a guard, use in-memory “this fingerprint has a 1M graph” from
`bandwidth_data`, not filesystem stats.

---

## Implementation sequence

1. **This turn (landed):** plan + registry + cache key + CLI no-op +
   tests. Default `--charts off`. No HTML. No matplotlib import in
   the generate process.
2. **Renderer:** slim `render_relay_bandwidth_1m`. Mockup script may
   call it. Still default off; `auto` remains an explicit flag.
3. **Pass:** spawn pool, cache hit/miss, publish into `relay/<fp>/`
   after HTML. Measure cold vs warm. First run is a slice
   (`--charts-limit` / `--fingerprint`).
4. **HTML:** option C History `<img>` gated on charts actually running
   and a 1M graph for that fingerprint.
5. Keep default `off`. Do not flip to `auto` because the extra is
   installed.
6. **Next chart** via registry (uptime B, then sparks, then flags).

---

## Skeleton landed with this plan

- `allium/lib/charts/` — registry (`relay_bandwidth_1m`), cache key,
  identity (`url:` host), pipeline skip logic
- `allium/allium.py` — `--charts` / `--no-charts` / `--charts-limit` /
  `--fingerprint` / `--chart-workers`; `maybe_run_charts()` after
  HTML; default off is silent
- `config/requirements-charts.txt` — matplotlib extra, not a core dep
- Tests: `tests/unit/charts/`

No `relay-info.html` change. No matplotlib in `requirements.txt`.
`compare_outputs.py` is not required for this turn.
