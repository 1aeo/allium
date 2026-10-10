# Relay and operator history charts

Build-time SVG charts on relay and contact pages: throughput over a write/read
strip for 1M / 6M / 1Y / 5Y, Running-flag uptime for the same periods, and the
summed throughput of an operator's relays. No JavaScript and no extra
dependency: `allium/lib/charts/svg.py` writes the SVG text directly. Colors and
type follow the 1aeo.com/blog charts (dark `#1e1e1e` canvas, DejaVu Sans).

## Where they are written

- `allium.py` builds one `ChartWriter` (`charts/render.py`) before forking when
  `/bandwidth` or `/uptime` data is loaded (`--apis all`). It holds the cached
  fingerprint maps (`operator_analysis.history_maps`) and the 1M family and
  peer write/read medians, which need every relay.
- The relay page workers (`_RelayPageRenderer.write`) call
  `ChartWriter.relay()` and the contact page workers (`_render_contact_variants`)
  call `ChartWriter.contact()`. The SVGs land next to the page they belong to,
  so a page only references charts that were written.
- About 68k charts for the whole network take under a minute of CPU in those
  existing workers (about 1-3 ms each, about 9 KB each).
- `--no-charts` skips them.

## Content rules

- Copy: `outcome.py` (subtitles), `identity.py` (`nickname · url host`),
  frozen role bands in `data/role_ratio_bands.json` (do not recompute from the
  live dump).
- Each period only shows its own window, ending at Onionoo's `relays_published`.
- Bandwidth charts need a 1M history; family and peer medians are 1M only.
- Operator charts sum members on the most common sampling interval, compare
  write/read with the members' most common role, and are skipped for the
  group of relays without contact info.
