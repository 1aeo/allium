## DNS wildcard scan analysis (exitdnshealth.1aeo.com)

Time window and sample size
- Data source: https://exitdnshealth.1aeo.com/files.json
- 43 scans from 2026-01-19 21:18:09 UTC to 2026-01-22 08:15:01 UTC
- Median scan interval: 118.32 minutes (approx 2 hours)
- Min/max scan interval: 0.30 / 123.02 minutes (some rapid re-runs)
- Median relays per scan: 3138 (min 7, max 3149)
- Total relay results analyzed: 128,437

Overall outcomes (all scans)
- success: 108,763 (84.68%)
- relay_unreachable: 17,291 (13.46%)
- dns_fail: 1,414 (1.10%)
- timeout: 924 (0.72%)
- wrong_ip: 31 (0.02%)
- exception: 14 (0.01%)

Failure type classification (all non-success results)
- circuit_error (relay_unreachable, circuit errors): 17,291 (87.89%)
- dns_nxdomain: 1,414 (7.19%)
- dns_timeout: 924 (4.70%)
- dns_wrong_ip: 31 (0.16%)
- dns_exception: 14 (0.07%)

Top error strings (by count)
- Tor Circuit Error: Relay channel closed unexpectedly (13,624)
- Tor Circuit Error: Construction timed out (2,467)
- DNS Error: SOCKS 4 - Domain not found (NXDOMAIN) (1,414)
- Tor Circuit Error: Circuit was closed (1,184)
- DNS Error: Timeout (terminated during retry) (208)
- DNS Error: Expected 64.65.4.1, got 162.159.36.12 (31)

Relay stability categories (by fingerprint)
- Total relays seen: 3,164
- Always success: 8
- Always fail: 10
- Flapping (both success and failure): 3,146

Flapping categories (by failure types observed)
- circuit-only flapping: 2,162
- mixed (circuit + DNS failures): 976
- DNS-only flapping: 8

Volatility between consecutive scans
- Average status change rate between scans: 24.68% of relays
- 90.87% of all status transitions involve relay_unreachable
- Most common transitions: success <-> relay_unreachable

Failure streaks (per relay)
- 15,941 total failure streaks
- 13,328 streaks (83.6%) are single-scan only
- Longest observed streaks: 42 scans (a few relays fail in every scan)

DNS failures per relay
- Relays with any DNS failure: 993
- Relays with exactly 1 DNS failure: 686
- Relays with >=3 DNS failures: 178
- Relays with >=10 DNS failures: 39
- wrong_ip appears on only 1 relay across the window

Examples: same relays succeed and fail over time (flapping)
- Circuit-only flapping:
  - 88ABAA530BEF7CC4E15D3A8F7243540B288DBC91 (DFRI103): success 36, relay_unreachable 6
  - C8751E119536469668073F0769B84F30A98325E2 (r0cket06i2): success 34, relay_unreachable 6
  - 6E3DD22CF40499F67CCADC5C024397748C0E63B4 (artikel10ber34): success 38, relay_unreachable 3
- Mixed flapping (circuit + DNS):
  - E1134F39470C5E8486321EE05506D9A7D6528A6E (JohandExit): success 34, relay_unreachable 6, exception 1
  - ACB30ED82CA61B49E38E5969505D7E2F29897AA1 (Quetzalcoatl): success 32, relay_unreachable 6, timeout 1
  - 43A51C1DA7B16E39461208CF4E4FB80AD22892F5 (DFRI66): success 35, relay_unreachable 4, timeout 1
- DNS-only flapping (rare):
  - 69022EDC564591DDC51FAC44CC6937434754D231 (NLTorNiceVPSnet): success 22, dns_fail 19 (NXDOMAIN)
  - 1677C01D2E0A2FB0A4A674E45CCB8AE231654F89 (prsv): success 40, timeout 2
  - 0082C49022C0811D45620D408E068835E2BABA71 (HandsofGoldSpa): success 40, timeout 1

Examples: constantly failing relays (no successes)
- DNS NXDOMAIN dominant:
  - A7C7C73E27420DFF9BB3BA3AE395CDEAC3171FA3 (hellotor): dns_fail 38, relay_unreachable 4
  - 59A5F150E4D670325CE55A56999FEA8FE2B3D887 (PonyLV): dns_fail 36, relay_unreachable 6
  - 959C5935AA3BBC56E174B2DC30D6ABEA0A9914D4 (TheMadHackerNodeV5): dns_fail 35, relay_unreachable 7
- Wrong IP (persistent):
  - A510D4DFA81FD3CA07391600337BF6BA5A589A5D (ounfnegire): wrong_ip 31, dns_fail 3, relay_unreachable 7
- Circuit-only failure:
  - 88C7705BD78718BEF28C61A2AF6641488321DE89 (unknown): relay_unreachable 4

## Recommendations: scan frequency and reducing volatility

Recommended frequency (based on observed volatility)
- Keep the full scan cadence at 2 hours. The observed median status change interval is also ~2 hours, so this cadence captures most changes without excessive load.
- Add a targeted recheck cycle for failed relays:
  - For any DNS failure (NXDOMAIN/timeout/wrong_ip), recheck that relay 15 to 30 minutes later.
  - Mark a relay as "confirmed DNS bad" only after 2 consecutive DNS failures (or 2 of 3 checks).
  - Treat relay_unreachable as "unknown" and recheck once; do not count it as DNS failure.

Why: 83.6% of failure streaks are single-scan only, and 90.87% of transitions involve relay_unreachable. A quick recheck reduces false positives without increasing the full-scan load.

Steps to reduce transient network volatility
1) Separate circuit errors from DNS health
   - Do not downgrade DNS health for relay_unreachable events.
   - Track a separate "circuit reliability" score.

2) Require multi-sample confirmation for DNS failures
   - Use consecutive failure rules (2-in-a-row) before flagging.
   - For wrong_ip, a single confirmation is strong (only one relay observed, persistent across scans).

3) Multi-circuit and multi-query checks per relay
   - On DNS failure, retry via a fresh circuit or first-hop selection.
   - Use multiple randomized subdomains to avoid single-name caching artifacts.

4) Grace period and decay for state changes
   - Promote to "bad" only after sustained failures.
   - Recover to "good" after a success, but keep a short cooldown (e.g., require one extra success) to avoid rapid flapping.

5) Adaptive scanning
   - Keep the 2-hour full scan.
   - Trigger targeted retries only for non-success relays (cost-effective).

Summary recommendation
- Full scan every 2 hours, plus fast retries for failures.
- Confirm DNS failure with 2 consecutive DNS errors (4 hours maximum to confirm with current cadence), or faster if using 15-30 minute rechecks.
- This approach balances detection speed with high confidence in correctness.
