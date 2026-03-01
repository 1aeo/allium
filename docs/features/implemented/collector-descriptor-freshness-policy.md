# CollecTor Descriptor Freshness Policy (Implemented)

## Scope

This policy applies to `fetch_collector_descriptors()` in `allium/lib/workers.py`,
which feeds Happy Families classification data (`family_cert_groups`) into relay,
contact, family, and network health pages.

## Problem Addressed

CollecTor `recent/relay-descriptors/server-descriptors/` can occasionally lag for
hours while still returning successful HTTP responses. Without a freshness policy,
the pipeline could incorrectly downgrade relays from `family-cert` to `no-cert`
based on stale source windows.

## Data-driven thresholds

Thresholds were chosen from observed feed behavior:

- p50 inter-file gap: ~60 minutes
- p95 inter-file gap: ~172 minutes
- max observed gap: ~278 minutes (~4.6 hours)
- observed severe lag event: ~10 hours

### Source freshness states

- **fresh**: `source_age <= 2h`
- **degraded**: `2h < source_age <= 5h`
- **stale**: `source_age > 5h`
- **critical stale flag**: `source_age > 12h`

Where `source_age` is computed from the newest descriptor filename timestamp in
the CollecTor recent listing.

## Decision tree

1. **Hard failure** (timeout/error/no files/no parsed descriptors):  
   fallback to prior cached data (existing behavior).

2. **Stale source** (`>5h`) with valid prior cache:  
   keep prior cached status unchanged.

3. **Degraded source** (`2h..5h`):  
   allow upgrades, freeze downgrades:
   - keep prior cert/key mappings
   - add newly observed cert/key mappings
   - do not remove prior cert status

4. **Fresh source** (`<=2h`):  
   apply downgrade confirmation before removing cert status.

## Downgrade confirmation rules

For candidate downgrade (`prior cert` and `current no-cert`), require one of:

1. **Consecutive fresh observations**:
   - `count >= 2` fresh runs seeing no-cert

2. **Published timestamp delta**:
   - no-cert descriptor `published` timestamp is at least **20 hours**
     newer than known cert evidence

Until confirmed, prior cert status is retained.

## Metadata stored in descriptor cache

`collector_descriptors.json` now includes:

- `source_latest_file_ts`
- `source_age_hours`
- `source_freshness`
- `source_critical_stale`
- `hf_transition_state`
  - `pending_no_cert` (per-relay downgrade counters)
  - `last_cert_published` (last known cert evidence)

These fields are additive and backward-compatible with older cache files.

## Output compatibility

The policy preserves existing downstream interfaces:

- `family_cert_fingerprints`
- `all_seen_fingerprints`
- `family_cert_groups`
- `coverage_hours`
- `fetched_at`

No template or page-writer interface changes are required.
