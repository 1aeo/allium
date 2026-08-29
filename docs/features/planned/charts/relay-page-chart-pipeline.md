# Relay-page chart pipeline

**Encoding** (identity, C copy, bands): locked in
[`allium/lib/charts/outcome.py`](../../../../allium/lib/charts/outcome.py)
(C copy), [`identity.py`](../../../../allium/lib/charts/identity.py), and
[`bands.py`](../../../../allium/lib/charts/bands.py).
**Shipped bands**: [`allium/lib/charts/data/role_ratio_bands.json`](../../../../allium/lib/charts/data/role_ratio_bands.json).

How `relay_bandwidth_1m` is drawn after HTML without putting matplotlib on the Jinja path.

| Piece | Choice |
|-------|--------|
| When | After `generate_site()`. Not inside Jinja or `write_relay_info()`. |
| How | `multiprocessing` **spawn**, default `min(4, cpu)`, cap 8. Slim picklable jobs. |
| Cache | SHA-256 of fields that change pixels. `{output}/.chart-cache/`. |
| Publish | Hardlink/copy to `www/relay/<fp>/bandwidth-1m.png` after HTML. |
| Deps | matplotlib extra (`config/requirements-charts.txt`). Core generate is Jinja2-only. |
| CLI | `--charts {off,auto,on}` **default `on`**. `--no-charts` turns it off. Ramp with `--charts-limit N` and `--fingerprint FP`. |
| HTML | History `<img>` only when the pass will run **and** that fingerprint is in the sliced 1M set. |

Same-day rebuilds that only tick votes / uptime / `last_seen` must not redraw ~7k figures.

## Generate facts that constrain the design

- Group pages use a **fork** pool (`--workers`, often 8–16). Those workers stay Jinja-only.
- `write_relay_info()` is sequential and **`rmtree`s `www/relay/`** each run. A PNG written before that, or left from yesterday, is gone. Charts publish **after** HTML.
- `--apis details` has no `/bandwidth`. Charts skip with one line; HTML still succeeds.
- `process_all_bandwidth_data_consolidated()` keeps averages, not `1_month` arrays. Charts read `relay_set.bandwidth_data` via `allium.lib.bandwidth_utils.build_bandwidth_map()`. Do not attach 1M arrays to every relay dict for Jinja. Onionoo timestamps and `published_clock` live in `allium.lib.time_utils`.
- `1_month` write/read is daily (`interval` 86400). A warm 12-hour bandwidth cache is the main cache hit.

| Role | Path |
|------|------|
| Durable cache | `{output}/.chart-cache/{chart_id}/{fingerprint}.png` + `.json` |
| Published file | `{output}/relay/{fingerprint}/bandwidth-1m.png` |
| `<img>` | `src="bandwidth-1m.png"` (same directory as `index.html`) |

Fingerprint path segments are 40-char hex only.

## Registry

`ChartSpec` and the registered period heroes live in
[`pipeline.py`](../../../../allium/lib/charts/pipeline.py)
(`chart_id`, output pattern, cache subdir, renderer, version). First id:
`relay_bandwidth_1m`. Later ids (uptime, sparks, flags, contact) register the
same way — no new CLI flags. `1m` / `6m` / `1y` / `5y` share the bandwidth
renderer.

## CLI

```
--charts {off,auto,on}     default: on; bare --charts means on
--no-charts                store off
--charts-limit N           first N chartable relays (0 = no limit)
--fingerprint FP           repeatable
--chart-workers N          0 → min(4, cpu); hard cap 8
```

Do **not** reuse `--workers`. Do **not** flip the default to `auto`.

| Mode | extra missing | extra present |
|------|---------------|---------------|
| `off` | silent | silent |
| `auto` | silent | run |
| `on` | one line + install hint; HTML succeeds | run |

`--apis details`: skip, do not fail.

`apply_chart_html_flags()` lives in
[`relays.py`](../../../../allium/lib/relays.py)
(next to other `relay_set` HTML gates) and runs **before** Jinja so History
`<img>` is omitted unless the later pass will run (matplotlib present, bandwidth
data, that fingerprint selected). Limit / fingerprint slices match the later
pass. `--charts on` without matplotlib: one log line, skip figures, omit the
img. The chart pass may re-export the function.

## Pass

1. HTML finished. `www/relay/` is a fresh tree.
2. `build_bandwidth_map` once. Role medians once; family medians once per `effective_family` (omit operator line when n&lt;2). Contact/AROI is identity text, not the overlay group.
3. For each selected relay with a 1M graph: hash payload; hit → publish; miss → spawn job.
4. Each job is try/except. Pool death does not fail HTML.
5. Progress via `log_without_increment` (does not change the HTML step count).

Use **spawn**. Initializer: `matplotlib.use("Agg")` then pyplot. Never import matplotlib in the HTML parent.

## Cache key (`relay_bandwidth_1m`)

Canonical JSON: `sort_keys=True`, `separators=(",", ":")`, `allow_nan=False`. Schema version `3`.

**In the key:** `schema_version`, `chart_id`, `renderer_version`, `fingerprint`, derived `currently_overloaded` (not raw `relays_published`), identity (`nickname`, `operator`), `advertised_bandwidth`, sorted `flags`, `role`, `last_restarted`, overload timestamps, `write_1m` / `read_1m` (`first/last/interval/factor/values`, nulls kept), overlays, `bands` (role + typical/invest + n), `bands_frozen_from`.

**Not in the key:** votes, `last_seen`, `observed_bandwidth`, uptime %, consensus weight, AS, raw contact, platform, country, raw `relays_published`, `--display-bandwidth-units` (the figure is always Mbit/s).

Hit: sidecar `key` matches **and** cached PNG size &gt; 0. Then hardlink/copy into the fresh relay directory.

## Extra

```
pip3 install -r config/requirements-charts.txt
```

Detect with `importlib.util.find_spec("matplotlib")`. matplotlib 3.8 dropped Python 3.8 — pin `3.7.x` on 3.8. Do not add matplotlib to `requirements.txt`.

## Adding a chart

Register a `ChartSpec`, write `render_<id>(job)`, add a template slot, extend the payload. Same pool and cache root.

## Rejected

Matplotlib inside relay HTML workers. One megaplot. Client-side Chart.js/D3. SVG-via-Jinja as the first bandwidth chart. In-template `os.path.exists` on 7k files.

Code: `allium/lib/charts/`. Tests: `tests/unit/charts/`.
