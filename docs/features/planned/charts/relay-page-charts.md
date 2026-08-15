# Relay page charts

**Audience**: Contributors
**Scope**: Time-series charts on the individual relay page (`relay-info.html`)
**Status**: Variation review — pick encodings, then implement
**Data**: Onionoo `relays_published` 2026-08-15 06:00 UTC

This is page type 1. Network-health, contact, country, and AS pages come after
the encodings here are chosen.

Mockups: [`mockups/`](mockups/). Regenerator:
[`generate_relay_page_chart_variations.py`](generate_relay_page_chart_variations.py).

---

## What "same page: chart 1 and chart 3" meant

That line in [`top-10-operator-charts.md`](top-10-operator-charts.md) was
ambiguous. **Same page meant this page** — `relay-info.html` for one
fingerprint.

It proposed, after uptime and bandwidth:

1. Chart 1 (network CW vs observed-bandwidth scatter) as a small inset with
   this relay highlighted.
2. Chart 3 (network-wide Guard vs 2 MB/s histogram) as an eligibility bar.

Those two are the wrong next charts for a relay page.

- Chart 1 is a **network** chart. Rendering the same 8k-point scatter on
  ~11k relay pages wastes build time and does not help "what happened to
  *this* relay last week." A one-line percentile already exists in
  `#bandwidth` ("Consensus Weight … Nth pctl").
- Chart 3 is also a **network** chart. This page already has the right
  artifact: the `#flags` eligibility table (this relay vs authority
  thresholds). A histogram of every other relay does not answer "why did
  *I* lose Guard?"

Correct split:

| Chart from the top 10 | Relay page | Later page |
|-----------------------|------------|------------|
| 5 Uptime history | Yes — `#uptime` | Contact overlay |
| 6 Bandwidth history | Yes — `#bandwidth` | Contact overlay |
| Flag flapping (new) | Yes — `#flags` | Contact overlay |
| 1 CW vs bandwidth scatter | Percentile only | Network health |
| 3 Guard eligibility histogram | Table already there | Network health |
| 2 / 4 / 7 / 8 / 9 / 10 | No | Country / AS / network health |

---

## What the relay page already shows (scalars)

`#flags`, `#bandwidth`, and `#uptime` already answer the snapshot questions.
Nothing below replaces those tables.

| Section | What the operator sees today | What is missing |
|---------|------------------------------|-----------------|
| `#flags` | Current flags, authority vote counts, eligibility table | Whether Guard / Stable / HSDir **flapped** last month |
| `#bandwidth` | Observed / advertised / rate, bwauth median, CW fraction | Whether traffic **ramped, crashed, or went lopsided** |
| `#uptime` | 1M/6M/1Y/5Y percentages, last restarted, overload badge | **When** the gaps happened, and whether they were restarts |

Allium already fetches Onionoo `/uptime` (including `flags.*`) and
`/bandwidth`. It then **collapses the series to averages and totals** in
`uptime_utils.py` / `bandwidth_utils.py` and drops the arrays. Charts need
those arrays kept for `1_month` (and optionally `6_months`) on the relay
object at render time.

---

## The three time-series that belong here

Live examples use two relays:

- **th4r** (`27A0…6242`) — Guard in DE. Process last restarted 2025-10-01.
  Five 4-hour Running gaps in the last month. **HSDir is currently missing**
  and has been dropping for days after each gap.
- **F3Netze** (`3C89…03F7`) — Exit+Guard in DE. Last restarted 2026-07-27.
  Overload timestamp 2026-08-13 05:00 UTC. Read/write stay near 1:1 around
  300–530 Mbit/s, about 54% of advertised 804 Mbit/s.

### R1. Uptime (Running flag) — three encodings

Same data: th4r `uptime.1_month`, 186 four-hour buckets.

#### A — Annotated line

Each gap labeled with time and depth. Good when there are three or four
events. Does not scale if the relay is flapping daily (labels collide).
Does not teach the 95% WFU threshold.

![Uptime A — annotated line](mockups/relay_uptime_a_annotated_line.png)

#### B — Area + 95% threshold (recommended default)

Fill the line, dash 95%, shade only the buckets that fall through. The
operator question is "did I spend time in the zone that costs Stable /
Guard / HSDir?" This answers it at a glance, and still looks calm when
the relay is at 100%.

![Uptime B — area + 95% threshold](mockups/relay_uptime_b_area_threshold.png)

#### C — Time-of-day heatmap

Rows are days (newest on top), columns are Onionoo's 4-hour UTC windows.
A nightly cron lights up one column. th4r's five dips sit at 10:00 / 14:00
/ 18:00 UTC — not a 04:00 restart job.

![Uptime C — time-of-day heatmap](mockups/relay_uptime_c_heatmap.png)

**Recommendation:** ship **B** in `#uptime`. Offer **C** as a "time of day"
toggle for operators who suspect a scheduled restart. Do not ship A as the
default.

---

### R2. Bandwidth (read / write) — three encodings

Same data: F3Netze `read_history.1_month` / `write_history.1_month` (daily
buckets). Vertical marks are `last_restarted` and `overload_general_timestamp`.

#### A — Dual line

Classic. Best at showing whether the two series track. Auto-scaled y-axis
makes the wiggle readable; it hides "how full is the pipe."

![Bandwidth A — dual line](mockups/relay_bandwidth_a_dual_line.png)

#### B — Overlapping area + ratio strip (recommended default)

Top panel is volume. Bottom strip is the operator question from the lists:
is outbound 5–10× inbound? Green band is 0.8–1.25. F3Netze stays inside
it (mean write/read = 1.03). A real imbalance would leave the band and
stay there.

![Bandwidth B — area + ratio](mockups/relay_bandwidth_b_area_ratio.png)

#### C — Daily bars vs advertised

Answers a different question: "I have a 1 Gbps VPS, why is metrics so
low?" F3Netze advertises 804 Mbit/s and delivers ~435 Mbit/s write (54%).
The complaint case is a bar chart that never approaches the dashed line.

![Bandwidth C — bars vs advertised](mockups/relay_bandwidth_c_bars_advertised.png)

**Recommendation:** ship **B**, and steal C's advertised dashed line onto
B's top panel. A is the fallback if we want the smallest possible SVG.
Daily Onionoo buckets hide intra-day spikes; a persistent 5× split still
shows on the ratio strip.

Empty state: a two-day relay such as PirateyMatey (CW 1) should say
"not enough history" rather than draw two dots.

---

### R3. Flag flapping — the chart the scalars cannot replace

Onionoo `/uptime` already has per-flag histories: `flags.Running`,
`flags.Guard`, `flags.Stable`, `flags.HSDir`, `flags.Exit`, `flags.Fast`.
Allium averages them into "Flag Uptime 1M/6M/1Y/5Y". That is why th4r
can look like "99% uptime" while HSDir is gone.

#### A — Presence swimlane (recommended)

One row per flag. Green = present for the whole 4-hour window, cream =
absent. th4r: Running / Guard / Stable stay green except four hairline
gaps. HSDir drops for **days** after each gap (Jul 19, Jul 30, Aug 11)
and is still missing. That is the mailing-list "I lost HSDir / Guard
after a blip" thread, drawn.

![Flags A — swimlane](mockups/relay_flags_a_swimlane.png)

#### B — Overlay lines

Same data. HSDir divergence is obvious, but Running / Guard / Stable sit
on top of each other at 99% and hide the gaps that triggered the loss.

![Flags B — overlay](mockups/relay_flags_b_overlay.png)

**Recommendation:** ship **A** under `#flags`, below the eligibility
table. Show Running plus the role flags this relay has ever held in the
window (Guard / Exit / Stable / HSDir). Skip Valid / V2Dir / Fast unless
they diverge from Running.

---

## Other relay-page charts — yes, later, or never

| Idea | Verdict | Why |
|------|---------|-----|
| Flag flapping | **Yes — R3** | Onionoo already has it; scalars hide it |
| Overload / restart markers | **Yes — on R1/R2** | Point timestamps, not their own chart |
| Advertised vs delivered | **Yes — line on R2** | Same bandwidth series |
| This relay vs network CW/BW | Later, one percentile | Full scatter is a network-health chart |
| Guard eligibility histogram | No | Table already answers "why no Guard" |
| Consensus-weight over time | Not from Onionoo | Needs CollecTor / ClickHouse |
| Observed-bandwidth over time | Not from Onionoo | `/bandwidth` is traffic, not `observed_bandwidth` |
| IPv6 reachability over time | Not from Onionoo | Snapshot diagnostic only |
| Per-authority vote history | Later | CollecTor votes; current table is enough |
| Family / version / ORPort | No chart | Already diagnostics in `#status` |

Do not restart to clear overload (list advice). The markers exist so the
operator can see that a restart and a flag loss are the same event — or
are not. th4r's gaps are **not** restarts.

---

## Where they sit on the existing page

```
#status          health grid          — no new chart
#connectivity    addresses / IPv6     — no new chart
#flags           eligibility table    — then R3 swimlane
#bandwidth       capacity + bwauths   — then R2 area + ratio
#uptime          1M/6M/1Y/5Y scalars  — then R1 area + 95%
                 overload subsection  — markers on R1/R2, not a third plot
```

Progressive enhancement: the tables stay if the SVG is missing. Period
toggle (1 month / 6 months) can wait until the encodings are chosen.

---

## Implementation notes (after encoding pick)

1. Keep `1_month` (optionally `6_months`) `values` + `first` + `interval`
   + `factor` on the relay for uptime, per-flag uptime, and read/write.
   Drop 1-year / 5-year arrays after the scalars are computed.
2. Render **build-time SVG** in the Jinja templates. One static Chart.js
   on 11k pages is the wrong default for a static site.
3. Reuse the colorblind palette already in the mockups (blue / vermillion
   / green / orange).
4. Generate `www_baseline` / `www_after` and run `compare_outputs.py`
   before merging — every relay HTML page will change.

---

## How to regenerate

```bash
python3 docs/features/planned/charts/generate_relay_page_chart_variations.py
```

Requires the Onionoo snapshots already used by
[`generate_onionoo_chart_mockups.py`](generate_onionoo_chart_mockups.py)
(`/tmp/onionoo/details.json`, `uptime_examples.json`,
`bandwidth_examples.json`).
