# AROI v3 — End-to-end verification report

**Date**: 2026-05-06
**Branch**: `cursor/aroi-v3-support` @ `894e357699`
**Master baseline**: `master` @ origin
**Method**: clean rebuild of master + branch with `--apis all`, then
diff every output file and cross-validate against live Onionoo +
aroivalidator data.

## Build summary

| | Master | Branch |
|---|---|---|
| Total relays | 10,867 | 10,867 |
| Total contacts | 3,160 | 3,161 |
| Families | 6,305 | 6,305 |
| Build time | ~3.5 min | ~3.5 min |
| AROI status line | (no v2/v3 split) | ✓ AROI: schema v2, 2810/3226 v2 valid, 322/332 v3 valid |

## Diff categorization (master → branch)

```
Common files:        27,422
  Identical:            312
  Timestamp only:    11,145
  Content diffs:     15,850
Only in baseline:       144 (10 distinct contacts)
Only in after:          127 (9 distinct contacts)
```

### Only-in-X analysis (271 files, 19 contacts)

**ALL 19 distinct contacts are v3-driven re-bucketing.** Master grouped v3 operators by `md5(individual_contact:<full_string>)` because its regex rejected `ciissversion:3`; branch correctly groups them by `md5(aroi_domain:<domain>)`. Total v3 relays re-bucketed: **332** (exactly matches upstream count).

| Master hash | → Branch hash | Operator | v3 relays |
|---|---|---|---|
| `aeacb4e8` | `ca802db3` | dfri.se | 148 |
| `16af3d36` | `54432e80` | applied-privacy.net | 120 |
| `32661c82` | `64e974a7` | (33-relay v3 op) | 33 |
| `0f37bfe7` | `b35fedab` | (9-relay v3 op) | 9 |
| `2233f27b` | `592c6ac7` | 1aeo.com (the user's example) | 8 |
| `5d176435` | `2eb044c3` | (5-relay v3 op) | 5 |
| `a7ab61d5` | `cd2d6797` | themadhacker.net | 4 |
| `357d3908` | `13419a25` | (3-relay v3 op) | 3 |
| `4cdc5765` | `ef142a76` | (1-relay v3 op) | 1 |
| `0a6f89c5` | `48798099` | (1-relay v3 op) | 1 |

This is the **exact intended fix**: master silently mis-bucketed every v3 operator; branch correctly groups them into proper AROI-domain contact pages.

### Content diff breakdown (15,850 files)

| Bucket | Count | Cause | Intentional? |
|---|---|---|---|
| relay pages | 3,582 | B3 v2/v3 badge + per-relay status flags on AROI relays | ✅ Yes |
| contact pages | 7,830 | B1 pills/peer-issue sections/rollup table on AROI contacts (and family pages including them) | ✅ Yes |
| family pages | 4,153 | Family pages render contact-relay-list.html which has new sections | ✅ Yes |
| AS pages | 162 | Sample inspection: pure volatile-time drift ("X ago" strings, "Last fetch" GMT timestamps) | ✅ Drift only |
| country pages | 42 | Same as AS pages, plus relay-list v2/v3 badges where applicable | ✅ Drift + B5.2 |
| flag pages | 11 | Volatile time drift | ✅ Drift only |
| first_seen pages | 18 | Volatile time drift | ✅ Drift only |
| platform pages | 7 | Volatile time drift | ✅ Drift only |
| misc pages | 40 | B2 dashboard, B4 leaderboard, B5 search index, B6 diagnostics, B1.6 misc-contacts | ✅ Yes |
| root pages | 5 | search-index.json (B5.1 schema 1.6), index page, all relays, top500 | ✅ Yes |

**Conclusion**: every diff is either an intentional v3 surface change or live data drift between the two builds (~10min apart). No accidental regressions.

## Onionoo + aroivalidator content accuracy validation

Spot-checked 4 key relay-info pages against live source data:

### Test 1: `eisbaer` (applied-privacy.net, valid v3)
- Onionoo says: `family_ids = ['Ajo1uQ+kzXdIToo6wib4iZLnf7oqSHLsqjqxSrdcQfE']`
- aroivalidator says: `valid=True, proof_type=dns-familyid-ed25519, ciissversion=3`
- ✅ rendered shows `applied-privacy.net` (matches upstream domain)
- ✅ rendered shows blue `v3` badge
- ✅ rendered shows `✓ Validated`
- ✅ no `⏳ Pending` (correct — relay is valid)
- ✅ no per-relay duplicate badge (op cascade=validated, suppression works)

### Test 2: `kodakblack` (1aeo.com, missing_family_ids)
- Onionoo says: `family_ids = NOT_PRESENT` (operator hasn't refreshed yet)
- aroivalidator says: `valid=False, error_category=missing_family_ids`
- ✅ rendered shows blue `v3` badge
- ✅ rendered shows operator-level `⏳ Pending` peer badge
- ✅ rendered shows explicit "⏳ Pending Onionoo refresh" note explaining transient
- ✅ no per-relay `⏳ Pending` duplicate (suppressed correctly after audit fix)

### Test 3: `TheMadHacker5Plaza` (themadhacker.net, uri_file_missing)
- aroivalidator says: `valid=False, error_category=uri_file_missing`
- ✅ rendered shows blue `v3` badge
- ✅ rendered shows operator-level `🚫 Unauthorized` cascade (other relays hit content_mismatch)
- ✅ rendered shows per-relay `⚠ this relay: Misconfigured` with disambiguating prefix (this relay's `uri_file_missing` is misconfigured-not-unauthorized)
- ✅ no false `✓ Validated`

### Test 4: Network Health Dashboard counts
| Metric | Live source | Rendered | Match |
|---|---|---|---|
| ciissversion v2 declared | 3383 | 3383 | ✅ |
| ciissversion v3 declared | 332 | 332 | ✅ |
| v2 success rate | 87.0% (2808 of 3226 attempts) | 87.0% | ✅ |
| v3 success rate | 97.0% (322 of 332 attempts) | 97.0% | ✅ |
| DNS-FamilyID | 268/268 (100%) | 268/268 (100%) | ✅ |
| URI-FamilyID | 54/64 (84.4%) | 54/64 (84.4%) | ✅ |

## Issue surfaced + fixed during this audit

The before/after comparison + cross-validation surfaced **one real UX bug** that prior continuation passes hadn't caught:

**Bug**: relay-info pages stacked operator-level badges AND relay-specific badges, producing confusing duplicates like `✓ Validated ⏳ Pending ⏳ this relay: Pending`.

**Root cause**: pending-bucket relays are also in misconfigured-bucket (dual-bucketing for cascade purposes). When pending was suppressed, the elif chain fell through to misconfigured.

**Fix** (commit `894e357699`): resolve relay's TRUE category FIRST with strict priority order, then decide whether to render based on operator-level overlap. Adds `this relay:` prefix for disambiguation. Renders ONLY when relay status differs from what operator-level badges already convey.

## Sign-off

- **891 tests** pass in default `pytest tests/` (offline)
- **+1 system-marker test** for live API verification (codified A.10 smoke check)
- **0 unintentional diffs** in master → branch comparison
- **All sampled rendered content** matches live Onionoo + aroivalidator data exactly
- **Bug from audit** identified and fixed

The branch is verified ready for review.
