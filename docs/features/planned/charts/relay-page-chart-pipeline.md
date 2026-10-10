# Relay-page chart pipeline

Option B period heroes after HTML. Matplotlib never imports on the Jinja /
`write_relay_info` path. Encoding locks: C copy in `outcome.py`, identity in
`identity.py`, frozen bands in `data/role_ratio_bands.json` (do not recompute
from the live dump).

## Constraints

- After `generate_site()`. `write_relay_info()` `rmtree`s `www/relay/` — publish after HTML.
- Spawn pools after HTML (`--chart-workers`, default `min(cpu, 16)`, cap 16). Four date-range runners (1M / 6M / 1Y / 5Y) share that single process budget — never 4×N. Do not reuse `--workers` (HTML fork pool). Matplotlib Agg initializer; matplotlib must not enter Jinja.
- `--charts` default `on`; `--no-charts`; slice with `--charts-limit` / `--fingerprint`.
- `--apis details` has no `/bandwidth`: skip, HTML succeeds.
- Read history via `build_bandwidth_map` + `series_by_fp`. Do not attach 1M arrays to every relay dict.
- Cache: SHA-256 of drawn fields, schema 3, `{output}/.chart-cache/`. Not in the key: votes, `last_seen`, uptime, raw `relays_published`, `--display-bandwidth-units`.
- HTML flags (`apply_chart_html_flags` on `relays.py`) run before Jinja. Thin periods omit PNG, spark link, and extra HTML.
- Family/peer overlays are 1M-only. 6M/1Y/5Y reuse the same hero renderer; sparks are CSS-scaled links to `index.html` / `6m.html` / `1y.html` / `5y.html`.

## CLI

`--charts {off,auto,on}` (bare `--charts` = on), `--no-charts`, `--charts-limit N`, `--fingerprint FP`, `--chart-workers N`.

| Mode | extra missing | extra present |
|------|---------------|---------------|
| `off` / `auto` | silent | `auto` runs |
| `on` | one line + install hint | run |

`pip3 install -r config/requirements-charts.txt`. Detect with `find_spec("matplotlib")`. Pin `3.7.x` on Python 3.8.

`ChartSpec` and the four period heroes live in `pipeline.py`. Same pool and cache root for new ids.

## Contact / operator charts

After HTML (same `maybe_run_charts` pass). `write_pages_by_key` `rmtree`s
`www/contact/` — publish PNGs only under `contact/{contact_md5}/….png`.
Contact ids are 32-hex MD5 (`contact_md5`); they never go through
`is_relay_fingerprint`. `--charts-limit` / `--fingerprint` still slice
relays; chart operators that include those fingerprints. No `--contacts-limit`.

`contact.html` uses `src="{{ page_ctx.path_prefix }}contact/{{ value }}/….png"`
so vanity copies become `../contact/{hash}/….png` via `adjust_vanity_paths`.
Series: timestamp-aligned **sum** of member write/read. Do not invent 1M
when no member has `1_month`. No extra Onionoo or datastore.
