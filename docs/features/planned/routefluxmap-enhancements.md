# RouteFluxMap integration enhancements

**Audience**: Contributors
**Scope**: Optional JSON exports and map layers on top of the Allium pages and RouteFluxMap links that already ship. The interactive geographic map is the RouteFluxMap site.
**Status**: Proposed. Nothing in this document is implemented in Allium.

## How to Verify

Links that already exist:

```bash
rg -n "routefluxmap" allium/templates/skeleton.html allium/templates/country.html allium/templates/relay-info.html
rg -n "country.upper" allium/lib/relays.py
```

Data this plan would add, which is absent today:

```bash
rg -n "SharedDataExporter|classifications.json|aroi-operators.json|country-rarity" allium
```

Generated paths to check against `allium/lib/categorization.py` (`sort_relay(..., "as", relay.get("as"), ...)`) and `allium/lib/page_writer.py` (`write_pages_by_key`):

- `country/<ISO>/index.html` with an uppercase ISO code (`relay["country"]` is uppercased in `Relays._preprocess_template_data`)
- `relay/<fingerprint>/index.html`
- `as/<as>/index.html`, where `<as>` is the Onionoo `as` value (`AS` plus digits). Example data uses `AS36849` in `docs/development/example-data/1aeo_relays_data.json`. The public directory is `/as/AS6939/`, which is the shape `docs/reference/output-structure.md` records.

## What is already live

Allium links to RouteFluxMap, and RouteFluxMap links back to Allium metrics pages.

| Direction | Where | URL |
|-----------|--------|-----|
| Allium nav and footer | `allium/templates/skeleton.html` | `https://routefluxmap.1aeo.com` |
| Country page | `allium/templates/country.html` | `https://routefluxmap.1aeo.com/#CC=<ISO>` |
| Relay page | `allium/templates/relay-info.html` | `https://routefluxmap.1aeo.com/#relay=<fingerprint>` |
| RouteFluxMap country tooltip | `src/lib/config.ts` `getCountryMetricsUrl`, used by `src/components/map/CountryLayer.tsx` and `src/lib/hooks/useCountryHover.ts` | `{PUBLIC_METRICS_URL}/country/<ISO>/` |
| RouteFluxMap relay popup | `getRelayMetricsUrl`, used by `src/components/ui/RelayPopup.tsx` | `{PUBLIC_METRICS_URL}/relay/<fingerprint>` |

`#CC=` and `#relay=` are RouteFluxMap hash parameters (`src/lib/utils/url.ts` in that repo). Allium writes the country code in uppercase. `allium/lib/country_utils.py` documents that choice so the country hash matches RouteFluxMap.

RouteFluxMap's country choropleth is client counts. `CountryLayer.tsx` calls `getCountryClientData` and sqrt-scales the fill from `#1a1a2e` to `#00ff88`.

Older Allium proposals still sketch a map rendered inside this site: `milestone-1-graphs-charts.md` (`GeographicHeatMap`, `allium/templates/geographic_heatmap.html`), `visualization-dashboard-proposal.md`, and `allium-roadmap-2025.md`. Those templates and modules are absent from the tree. This document is the follow-on for the RouteFluxMap site that is already linked.

## 1. Shared country-rarity export

Allium's country rarity is a weighted score in `allium/lib/country_utils.py`, computed by `get_rare_countries_weighted_with_existing_data(country_data, total_relays, min_score=6)`.

```text
score = (relay_count_factor * 4)
      + (network_percentage_factor * 3)
      + (geopolitical_factor * 2)
      + (regional_factor * 1)
```

A country is in the returned rare set when `score >= 6`. The factors are `calculate_relay_count_factor`, `calculate_network_percentage_factor`, `calculate_geopolitical_factor`, and `calculate_regional_factor` in the same file. The rare set is recomputed from the current relay census, so a static list of country codes would be wrong on the next run.

`FRONTIER_COUNTRIES` is a separate static set used by `is_frontier_country`:

```text
KZ, LK, MD, MK, MN, MT, TN, UY
```

AS rarity is a different scale. `assign_as_rarity_tier` maps a 0–5 AS score to `legendary`, `epic`, `rare`, `emerging`, and `common`. Those names apply to autonomous systems. The country file uses the weighted score and the frontier set. RouteFluxMap chooses any overlay colors when it reads the file.

Proposed file, written on each site build (not shipped today):

```text
{output}/shared/country-rarity.json
```

`--out` defaults to `./www` (`allium/allium.py`).

```json
{
  "min_score": 6,
  "frontier_countries": ["KZ", "LK", "MD", "MK", "MN", "MT", "TN", "UY"],
  "countries": {
    "CC": {
      "relay_count": 0,
      "rarity_score": 0,
      "rare": false,
      "frontier": false
    }
  }
}
```

`CC` is an uppercase ISO code. `relay_count` is `len(sorted["country"][cc]["relays"])` when that key exists, else `0`. `rare` is `rarity_score >= min_score`. Include a zero-relay code when the existing function would add it from `GEOPOLITICAL_CLASSIFICATIONS` (score still at least 6). `frontier` is membership in `FRONTIER_COUNTRIES`.

RouteFluxMap would fetch `{PUBLIC_METRICS_URL}/shared/country-rarity.json` and offer it as a second country fill beside the client-count ramp. That fetch is also not implemented. The live site returns 404 for `/shared/classifications.json`.

## 2. Validated-operator export

Operator rows are built by `_collect_operator_metrics` in `allium/lib/aroileaders.py`. Each value in the `aroi_operators` dict already has:

| Field | Meaning |
|-------|---------|
| `contact_hash` | Contact page key. Page path `contact/<contact_hash>/` |
| `aroi_domain` | Parsed AROI domain, or `none` |
| `total_relays` | Relay count |
| `total_bandwidth` | Contact-group observed bandwidth sum, bytes/s (`contact_data["bandwidth"]`) |
| `countries` | Sorted uppercase ISO codes |
| `validated_relay_count` | Relays that passed AROI proof checks |

`_rank_operators` returns 21 category lists (bandwidth, consensus weight, diversity, frontier builders, and the rest in that function). Each list is an independent top-50 ranking. A map badge uses one category's place in that list.

Proposed file:

```text
{output}/shared/aroi-operators.json
```

```json
{
  "operators": [
    {
      "contact_hash": "<contact_md5>",
      "aroi_domain": "example.net",
      "display_name": "<operator_key>",
      "total_relays": 0,
      "total_bandwidth": 0,
      "countries": ["DE", "US"],
      "validated_relay_count": 0,
      "fingerprints": ["<40 hex chars>"]
    }
  ]
}
```

Limit the array to operators with `validated_relay_count > 0` when the layer is validated operators only. That is the same predicate as the `validated_relays` leaderboard filter. `display_name` is the `operator_key` chosen in `aroileaders.py` (`aroi_domain` when it is not `none`, otherwise the incomplete-AROI fallback). `fingerprints` are the member relays' `fingerprint` values, collected in the loop that already walks `operator_relays`. RouteFluxMap already plots relays by fingerprint (`RelayPopup.tsx`). Join on that fingerprint. Allium relay pages store `latitude` and `longitude` from Onionoo, and RouteFluxMap geolocates with MaxMind on its own pipeline.

Clicking a highlighted marker should open `contact/<contact_hash>/`. A category rank, when shown, is the operator's place in one leaderboard list, linked to `index.html` or `misc/aroi-leaderboards.html` (the same template) at the category anchor, for example `#frontier_builders`.

## 3. AS metrics URL helper

RouteFluxMap has `getRelayMetricsUrl` and `getCountryMetricsUrl` in `src/lib/config.ts`. It has no `getASMetricsUrl`. `RelayPopup.tsx` does not render AS data. Adding the helper matters only after that popup shows an AS.

Allium's directory key is the Onionoo string. A live page is `https://metrics.1aeo.com/as/AS6939/`. `https://metrics.1aeo.com/as/6939/` and `https://metrics.1aeo.com/AS/6939` are not generated (both 404 on the public site). RouteFluxMap's note in `docs/features/future/relay-popup-enhancements.md` uses `/AS/` plus the digits with the `AS` prefix removed. That path does not match Allium.

Proposed helper for `src/lib/config.ts` in the RouteFluxMap repo:

```typescript
export function getASMetricsUrl(asNumber: string): string {
  const match = asNumber.match(/(\d+)/);
  if (!match) return `${config.metricsUrl}/misc/networks-by-bandwidth`;
  return `${config.metricsUrl}/as/AS${match[1]}/`;
}
```

The fallback is the generated network listing (`misc/networks-by-bandwidth.html`). The public host redirects that file URL to `/misc/networks-by-bandwidth`.

## Where an Allium exporter would run

Add `allium/lib/shared_data_exporter.py` and call it from `generate_site()` in `allium/lib/site_generator.py` after `write_relay_info()`, next to `generate_search_index()`. The exporter reads `relay_set.json` (country groups and relays) and the operator dict from `aroileaders.py`. It writes under `Path(args.output_dir) / "shared"`. No such module or `shared/` output exists.

```python
# Proposed sketch. This module is not in the repository.
# from pathlib import Path
def export_shared_data(relay_set, output_dir):
    shared_dir = Path(output_dir) / "shared"
    shared_dir.mkdir(exist_ok=True)
    # country-rarity.json  — country_utils score, min_score 6, FRONTIER_COUNTRIES
    # aroi-operators.json   — validated aroi_operators rows plus fingerprints
```

## Action items

| Task | Repo | Priority |
|------|------|----------|
| Add `allium/lib/shared_data_exporter.py` and call it from `generate_site()` | Allium | Later |
| Write `shared/country-rarity.json` using the weighted score and `FRONTIER_COUNTRIES` | Allium | Later |
| Write `shared/aroi-operators.json` for operators with `validated_relay_count > 0`, including fingerprints | Allium | Later |
| Optional country fill that reads `country-rarity.json` beside the client-count ramp | RouteFluxMap | Later |
| Highlight plotted relays whose fingerprint is in the operator export; link to `contact/<contact_hash>/` | RouteFluxMap | Later |
| `getASMetricsUrl()` returning `/as/AS<digits>/` | RouteFluxMap | Later |

## Related

- Live sites: https://routefluxmap.1aeo.com and https://metrics.1aeo.com
- Allium: https://github.com/1aeo/allium
- RouteFluxMap: https://github.com/1aeo/routefluxmap
- Working Allium features: [current capabilities](../../reference/current-capabilities.md)
- Generated paths: [output structure](../../reference/output-structure.md)
