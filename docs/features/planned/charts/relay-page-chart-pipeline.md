# Relay and operator history charts

Build-time SVG charts on relay and contact pages: throughput over a write/read
strip for 1M / 6M / 1Y / 5Y, Running-flag uptime for the same periods, and the
summed throughput of an operator's relays. No JavaScript and no extra
dependency: `allium/lib/charts/svg.py` writes the SVG text directly. Colors and
type follow the 1aeo.com/blog charts (dark `#1e1e1e` canvas, DejaVu Sans).

`--chart-format png` writes the same SVG rasterized at its own size (1080 px
wide) by the optional CairoSVG instead, for browsers with SVG off (Tor
Browser's Safest level). It needs `pip install cairosvg`, the cairo library
and the DejaVu Sans font (`allium.py` checks before fetching anything), and
costs about 30 ms and 58 KB per chart (about 4 GB for the network) against
about 1 ms and 9 KB for SVG.

## Where they are written

- `allium.py` builds one `ChartWriter` (`charts/render.py`) before forking when
  `/bandwidth` or `/uptime` data is loaded (`--apis all`). It holds the cached
  fingerprint maps (`operator_analysis.history_maps`) and the 1M family and
  peer write/read medians, which need every relay.
- The relay page workers (`_RelayPageRenderer.write`) call
  `ChartWriter.relay()` and the contact page workers (`_render_contact_variants`)
  call `ChartWriter.contact()`. The charts land next to the page they belong to,
  so a page only references charts that were written. They return
  `{period: height}` (one per chart type) so the page reserves every image's
  box before it loads.
- About 68k charts for the whole network take under a minute of CPU in those
  existing workers (about 1-3 ms each, about 9 KB each).
- A section shows its first period; the thumbnails link to `#bandwidth-6m`
  and so on, and CSS `:target` swaps the chart in place, so no page is
  copied per period and no JavaScript runs. `#1m`/`#6m`/`#1y`/`#5y` switch
  every chart on the page (empty `.chart-period` anchors placed before the
  chart sections, `chart_period_anchors`); a chart without that period keeps
  its default. These fragments are the deep links.
- `--no-charts` skips them.

## Content rules

- Copy: `outcome.py` (subtitles), `identity.py` (`nickname · url host`),
  frozen role bands in `data/role_ratio_bands.json` (do not recompute from the
  live dump).
- Each period only shows its own window, ending at Onionoo's `relays_published`.
- Family and peer medians are 1M only.
- Operator charts sum members on the most common sampling interval, compare
  write/read with the members' most common role, and are skipped for the
  group of relays without contact info.
