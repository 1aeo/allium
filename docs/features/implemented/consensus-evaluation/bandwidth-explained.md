# Understanding Tor Bandwidth Values

**Status**: Reference Documentation  
**Related**: [Consensus Evaluation README](./README.md)

---

## Overview

Tor relays have multiple bandwidth values that serve different purposes. This document explains what each value means, where it comes from, and how it's used.

---

## The Two Types of Bandwidth

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     BANDWIDTH DATA FLOW                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   YOUR RELAY                    BANDWIDTH AUTHORITIES                   │
│   ──────────                    ─────────────────────                   │
│       │                                │                                │
│       │ ① Relay publishes             │                                │
│       │   server descriptor           │                                │
│       │   with observed_bandwidth     │                                │
│       │                               │                                │
│       ├──────────────────────────────>│ ② Authority receives          │
│       │                               │   descriptor                   │
│       │                               │                                │
│       │                               ├──────────────────┐             │
│       │                               │ ③ sbws scanner   │             │
│       │                               │   measures actual│             │
│       │                               │   throughput     │             │
│       │                               │<─────────────────┘             │
│       │                               │                                │
│       │                               │ ④ Authority votes with:        │
│       │                               │   - Flags (uses observed_bw)   │
│       │                               │   - Consensus weight (measured)│
│       │                               │                                │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                        CONSENSUS                                │   │
│   │   • Flags = based on relay's observed_bandwidth                 │   │
│   │   • Weight = median of authority-measured values                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Bandwidth Values Explained

### 1. Relay-Reported Bandwidth (observed_bandwidth)

| Attribute | Value |
|-----------|-------|
| **Source** | Relay's server descriptor |
| **Measured by** | The relay itself |
| **Updated** | Every 18 hours (descriptor refresh) |
| **Used for** | Flag eligibility (Guard, Fast) |
| **API field** | Onionoo `observed_bandwidth` |

**What it represents**: The relay's self-reported bandwidth capacity based on its own measurements of recent traffic.

**Why it matters**: Directory authorities use this value to determine if a relay qualifies for:
- **Fast flag**: observed_bandwidth ≥ 100 KB/s OR in top 7/8ths of network
- **Guard flag**: observed_bandwidth ≥ 2 MB/s (AuthDirGuardBWGuarantee) OR in top 25%

---

### 2. Authority-Measured Bandwidth (consensus weight)

| Attribute | Value |
|-----------|-------|
| **Source** | Bandwidth authority's sbws scanner |
| **Measured by** | 6 of 9 directory authorities |
| **Updated** | Continuously (sbws runs ongoing measurements) |
| **Used for** | Path selection probability (consensus weight) |
| **Vote field** | `w Bandwidth=X` or `w Measured=X` |

**What it represents**: The actual throughput capacity measured by bandwidth authorities using standardized tests.

**Why it matters**: This determines how much traffic Tor clients send through your relay:
- Higher measured bandwidth = higher consensus weight = more traffic
- Tor uses the **median** of all authority measurements

---

## Why Are There Two Values?

### Trust Model

1. **Flag eligibility uses relay-reported bandwidth** because:
   - Flags are binary (you have it or you don't)
   - Self-reported bandwidth is "good enough" for qualification
   - Prevents gaming: you can't get more flags by lying about bandwidth

2. **Consensus weight uses authority-measured bandwidth** because:
   - Traffic distribution requires accurate values
   - Prevents relays from attracting more traffic than they can handle
   - Independent verification protects the network

### Which Authorities Measure Bandwidth?

| Authority | Runs sbws? | Location |
|-----------|------------|----------|
| bastet | ✅ Yes | US |
| dannenberg | ❌ No | DE |
| dizum | ❌ No | NL |
| faravahar | ❌ No | US |
| gabelmoo | ✅ Yes | DE |
| longclaw | ✅ Yes | US |
| maatuska | ✅ Yes | SE |
| moria1 | ✅ Yes | US |
| tor26 | ✅ Yes | AT |

**Note**: Authorities without sbws use the relay's advertised bandwidth directly, resulting in a default consensus weight of 10 KB/s in their votes.

---

## Common Questions

### Q: My observed bandwidth is 100 MB/s but consensus weight is only 5 MB/s. Why?

**A**: The consensus weight is what bandwidth authorities actually measured. Possible reasons for the discrepancy:
- Network conditions during measurement
- sbws testing from different geographic locations
- Relay bandwidth varying over time
- Measurement happens independently of your descriptor

### Q: I have high bandwidth but low Guard/Middle probability. Why?

**A**: Path selection probability depends on:
1. Your consensus weight (authority-measured)
2. Your flags (which relay roles you can serve)
3. Network-wide bandwidth weights

High observed bandwidth gets you flags, but path selection uses measured bandwidth.

### Q: Why does the 10 KB/s default appear for some authorities?

**A**: Authorities that don't run bandwidth scanners (dannenberg, dizum, faravahar) use a default value of 10 KB/s (10000 bytes/s) when they include the relay's advertised bandwidth instead of measured bandwidth.

### Q: Which value should I optimize for?

**A**: Both matter:
- **Observed bandwidth** (descriptor) → Determines flag eligibility
- **Actual throughput** → Determines what authorities measure → consensus weight

The best approach: ensure your relay can sustain the bandwidth you advertise.

---

## Data Sources Reference

| Value | Source | API/File | Field |
|-------|--------|----------|-------|
| observed_bandwidth | Onionoo | `/details` | `observed_bandwidth` |
| advertised_bandwidth | Onionoo | `/details` | `advertised_bandwidth` |
| consensus_weight | CollecTor | vote files | `w Bandwidth=X` |
| measured (sbws) | CollecTor | vote files | `w Measured=X` |
| flag-thresholds | CollecTor | vote files | `flag-thresholds` line |

---

## See Also

- [Consensus Evaluation Feature](./README.md)
- [Tor Directory Specification](https://spec.torproject.org/dir-spec/)
- [sbws Documentation](https://sbws.readthedocs.io/)

---

**Last Updated**: December 2024

