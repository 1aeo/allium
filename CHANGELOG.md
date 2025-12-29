# Changelog

All notable changes to Allium will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Consensus Evaluation Feature (Phase 1 & 2)

A comprehensive consensus troubleshooting system that helps relay operators understand how directory authorities view their relays.

**Relay Pages (`relay-info.html`)**:
- **Consensus Evaluation Section** - New section showing per-authority voting data
- **Summary Table** - Relay values vs. thresholds for all flag requirements (Guard, Stable, Fast, HSDir)
- **Per-Authority Table** - Detailed view of how each of 9 voting directory authorities sees the relay
- **Identified Issues** - Automatic detection of problems affecting relay status
- **Advice Messages** - Actionable suggestions for relay operators
- **Source Attribution Tooltips** - Hover over any value to see exact data source (e.g., "Source: CollecTor | File: vote | Field: stats wfu=X")

**Authorities Dashboard (`misc/authorities.html`)**:
- **Authority Health Monitoring** - Online status, latency, and voting status for all 9 authorities
- **Flag Thresholds Table** - Exact thresholds each authority uses for Guard, Stable, Fast, HSDir flags
- **Bandwidth Authority Detection** - Identifies which authorities run sbws bandwidth scanners
- **Dynamic Authority Discovery** - Authorities discovered from Onionoo (no hardcoded lists for display)

**New Modules** (`lib/consensus/`):
- `collector_fetcher.py` - Fetches and indexes CollecTor vote/bandwidth data
- `authority_monitor.py` - Monitors authority health and latency
- `consensus_evaluation.py` - Formats evaluation data for templates
- `flag_thresholds.py` - Centralized flag threshold constants and eligibility logic

**Technical Features**:
- O(1) relay lookup after initial indexing
- 1-hour cache for CollecTor data with 3-hour fallback
- 5-minute cache for authority health checks
- Feature flag: `ALLIUM_CONSENSUS_EVALUATION` (default: true)
- Graceful degradation when data unavailable
- Comprehensive error handling

**Data Sources**:
- CollecTor votes: Authority voting data, flags, thresholds
- CollecTor bandwidth: Bandwidth scanner measurements
- Onionoo details: Relay metadata, authority discovery

**Addresses Common Operator Questions**:
1. Why is my relay not in consensus?
2. Why did I lose my Guard/Stable/HSDir flag?
3. Which authorities can reach my relay?
4. What are the exact flag thresholds?
5. Why does my relay show different data on different sites?
6. Why is my consensus weight low?
7. IPv6 reachability issues
8. First seen date / Time Known reset
9. Is a specific authority having problems?
10. Flags gone after restart

### Changed

- Renamed internal "diagnostics" terminology to "consensus_evaluation" for clarity
- Environment variable: `ALLIUM_COLLECTOR_DIAGNOSTICS` → `ALLIUM_CONSENSUS_EVALUATION`
- Function names: `format_relay_diagnostics` → `format_relay_consensus_evaluation`
- Template variable: `relay.collector_diagnostics` → `relay.consensus_evaluation`
- Section anchor: `#consensus-diagnostics` → `#consensus-evaluation`

### Fixed

- HSDir TK default now matches Tor dir-spec (25 hours) instead of arbitrary 10 days
- Dynamic authority count (9 voting, 10 total with Serge who has Authority flag but doesn't vote)
- Authority latency checks now use dynamically discovered endpoints

### Documentation

- Added comprehensive user guide: `docs/features/implemented/consensus-evaluation/README.md`
- Documents all 13 common relay operator questions from tor-relays mailing list
- Documents all flag thresholds with sources (Tor dir-spec references)
- Documents data sources and refresh rates
- Documents all advice/issue messages

---

## Notes for Operators

### Enabling/Disabling the Feature

```bash
# Disable consensus evaluation
export ALLIUM_CONSENSUS_EVALUATION=false

# Enable (default)
export ALLIUM_CONSENSUS_EVALUATION=true
```

### Data Freshness

- CollecTor data refreshes hourly (matches Tor consensus cycle)
- Authority health refreshes every 5 minutes
- Check timestamps on pages for data age

### Understanding the Display

- **Green** values meet threshold requirements
- **Yellow/Orange** values partially meet requirements (some authorities)
- **Red** values are below threshold
- **Gray** values are not tested or not applicable

Hover over any value to see the exact data source via tooltip.

---

## Previous Versions

This is the first formal changelog. For previous changes, see git history.
