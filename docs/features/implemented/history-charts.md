# Relay and operator history charts

Build-time charts on relay and contact pages: throughput over a write/read
strip for 1M / 6M / 1Y / 5Y, Running-flag uptime for the same periods, and the
summed throughput of an operator's relays. No JavaScript. `allium/lib/charts/svg.py`
draws each chart as SVG text and records the same drawing calls. Colors and
type follow the 1aeo.com/blog charts (dark `#1e1e1e` canvas, DejaVu Sans).

PNG is the default, because Tor Browser's Safest level turns SVG off.
`charts/raster.py` replays the recorded calls with cairo at 2x (`--chart-scale`
1, 1.5 or 2; 2160 px wide, sharp on HiDPI screens) and writes the PNG itself.
By default every pixel is snapped to `raster.PALETTE`, 64 colors fixed in
advance: the charts' own named colors exactly, then the blended fills and edge
shades that cover the most pixels in real charts (`scripts/chart_palette.py`
picks them; `tests/unit/charts/test_raster.py` fails when a chart draws a color
the palette lacks). A 16 MB lookup table, built once before the page workers
fork, maps each pixel, a block of rows at a time so the work stays in the CPU
cache; the indexes are deflated (with zlib-ng when installed) into an 8-bit
palette PNG. In
~1,250 real charts 97.8% of pixels keep their exact color and 99% move by at
most 4 levels (of 255); a few antialiased edge pixels move further, so it looks
the same. `--chart-colors full` keeps every shade instead
(RGBA, every row "Up"-filtered with numpy).

Per chart at 2x with 4 workers busy: about 10.5 ms and 53 KB (full color: 10 ms
and 150 KB), against about 70 ms to rasterize the SVG text with CairoSVG at the
same size, and about 1 ms and 10 KB for SVG (`--chart-format svg`).

PNGs are cached in `data/cache/charts` under a hash of their drawing calls
(`Svg.ops`, exactly what cairo replays; the SVG text rounds them to 0.1 px), the
scale and the colors, and hard-linked next to their page. A chart that did not
change since the last build is linked, not drawn: most 6M/1Y/5Y charts, and 1M
charts between Onionoo's 4-hourly points (about 85% of all charts an hour
apart). A hit keeps the file's modification time, so `rsync -a` and HTTP caches
see it unchanged. `ChartWriter.sweep()` then deletes what the build did not
use, so the cache holds one copy of the current charts (about 3.6 GB; about 11 GB
in full color); an SVG build (`--chart-format svg`) deletes all of them. The cache
folder is named after `raster.VERSION` (replay code, background, palette, cairo
version, fonts found), so a change there starts a fresh cache. On 4 cores a full build
takes about 5m30s with an empty cache, then about 1m30s-2m on later builds, as
Onionoo adds a few points to each history (SVG: about 2m; full-color 1x PNG
drawn by CairoSVG took 9m41s).

The cost is page weight: a relay page with all eight charts loads about 415 KB
of PNG (1.2 MB in full color) against 80 KB of SVG, and with JavaScript off (Tor
Browser's Safest) `loading="lazy"` is ignored, so all of it loads with the page.
Thumbnails use the same files: separate small thumbnails would cut the first
view with JavaScript on, but add bytes at Safest, where hidden `<img>`s load
anyway.

PNG needs cairocffi and numpy (`config/requirements.txt`, where zlib-ng makes
deflate ~4x faster) plus the cairo library (`apt install libcairo2`).
`allium.py` checks before fetching anything: without them it writes SVG and
says so, or stops when `--chart-format png` was asked for. Without DejaVu Sans
(`fonts-dejavu-core`) cairo draws the text in another font; `allium.py` warns
when fontconfig's `fc-match` is installed to check.

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
- About 68k charts for the whole network, drawn in those existing workers.
- A section shows its first period; the thumbnails above it (four across the
  card's width) link to
  `#bandwidth-6m` and so on, and CSS `:target` swaps the chart in place, so no
  page is copied per period and no JavaScript runs. The thumbnails follow the
  charts in the HTML (the `~` selectors need that) but show above them, so the
  row stays in view when a click scrolls to the chart (keyboard and screen
  readers meet the chart first, then its thumbnails). `#1m`/`#6m`/`#1y`/`#5y` switch
  every chart on the page (empty `.chart-period` anchors placed before the
  chart sections, `chart_period_anchors`); a chart without that period keeps
  its default. These fragments are the deep links. On a relay page they land on
  the bandwidth chart card, past the bandwidth details above it: fixed offsets
  for the shortest details measured on every relay page (408 px from 992 px
  wide, 519 px below) put the card near the top, or up to about 280 px lower on
  a narrow phone, never past it. A relay page with only uptime charts does the
  same for the uptime card (366 / 580 px).
- `--no-charts` skips them.

## Content rules

- Copy: `outcome.py` (subtitles), `identity.py` (`nickname · url host`; for
  an operator its AROI domain, else its `url:` host, else its contact text, cut
  at a word when longer than 50 characters, and its relay count:
  `tor@kllx.eu · 64 relays`; relays without a contact, or with `none`, as the
  contact page treats them, are not an operator and get no chart),
  frozen role bands in `charts/data/role_ratio_bands.json` (`bands.py`; do not
  recompute from the live dump).
- Subtitles state facts about what the panel draws, so they hold by
  construction. Throughput: `Write avg 48 Mbit/s (44% of advertised), peak 170
  Mbit/s Sep 16` (the share only up to 100%: a period's mean is compared with
  today's advertised bandwidth). Write/read: the overall ratio (of sums, as the
  census) and its band, the days above p98 and below p2 listed per side (as a
  count past three runs, when the line would not fit, or when a typical
  overall ratio has most days out of band), then `out with the
  family` / `out with other Guards` when that median was beyond p2–p98 on the
  relay's side on at least half of those days, or `family and peers stayed in`
  when it was inside p2–p98 on at least half of them (out the other way: neither).
- Write/read is judged only on days with enough traffic to compare: some read,
  and a mean of write and read of 50 KB/s or more, the band census's cut (also
  the family and peer medians'). Other days leave the write/read line, its red,
  the spike callout and the subtitle, and stay in the throughput panel; a relay
  under 50 KB/s all period says so instead of drawing a line or the medians.
- The strip's 0.5 / 1.0 / 1.5 grid lines keep plain labels; `p10–p90` and
  `>p98` are named inside their own bands (beside the grid label where a band
  is too thin to clear it).
- Each bandwidth period only shows its own window, ending at the bandwidth
  document's `relays_published`. Onionoo adds no points once a relay is out of
  the consensus: for a relay no longer running (an operator with none
  running), the time axis runs on to that end, so the outage shows as a gap
  rather than a line reaching the right edge. A running relay's history only
  lags Onionoo's by a day or so; its axis ends just past its last point,
  unless the history ended over two slots and a day earlier (a stale Onionoo
  block), which shows as a gap too.
- Uptime charts use Onionoo's own window (`uptime_utils.block_window`: one
  calendar period ending at the latest consensus, on Onionoo's slot grid, taken
  from the uptime document's `relays_published`). An offline relay's history
  stops at its last consensus; the window's slots after it are drawn as Onionoo
  counts them (the first holds its last hours in the consensus, the rest 0%),
  and the "Average" is the relay page's figure for the period.
- Write/read is red where it leaves the role's p2–p98 band: the line's segments
  at an out-of-band day are drawn again in red, clipped to the strip beyond the
  band, so a day with no joined neighbour out on its side is a red tip, marked
  with a red dot too, as is a day less than 2 px past the band edge, where the
  red is only a sliver.
  A red line-and-dot legend entry, `Outside p2–p98`, explains them on the
  charts that draw them. A
  point with no neighbour to join (between gaps) is drawn as a short dash.
- A relay that relays.py finds overloaded gets a legend entry with its newest
  counted report: `currently overloaded · last report Sep 29, 22:00 UTC`
  (just `overloaded · …` for a relay no longer running, whose verdict comes
  from its last descriptor).
- Family and peer medians are 1M only. A family's median is over the members
  of the relay's effective family (Onionoo's families are mutual declarations,
  so members can list different sets), and is drawn only when 3 or more members
  count: a member counts on the 1M days it has both directions averaging at
  least 50 KB/s, as for the peer median, and the line is drawn only on days
  with 3 or more members counted. The median includes the relay itself,
  so with two members it would be the mean of this relay and the other, moving
  half as far as this relay.
- Operator charts sum members on the most common sampling interval, on days
  each member has both directions (as its own chart does), compare write/read
  with the role whose members carried the most traffic in the period (named in
  the strip's title, `vs Exit+Guard band`), and are skipped for the group of
  relays without contact info. Onionoo gives a relay no 1Y (or 5Y) history when its
  shorter one holds it whole, so such a member is summed from that shorter
  history, averaged into the period's slots (whole slots only). Members'
  histories reach the newest day at different times, so the sum stops at the
  newest slot every member still reporting (within two slots) has reached; a
  member no longer running does not hold it back, as its end is a real drop.
