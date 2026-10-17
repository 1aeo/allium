# TLS PQC scan (implemented)

Allium shows whether the latest Tor Network Health scan negotiated
`X25519MLKEM768`. The numbers come from that scan. A Tor version string is
not used: 0.4.8.17 can negotiate the hybrid only when it is built against
OpenSSL 3.5.0 or later. LibreSSL 4.3.0 implements ML-KEM-768, and current Tor
does not use that group (tpo/core/tor#41300).

## What the scanner writes

Margot's `tls-ciphers` command, on
[ahf/tls-ciphers-scanner](https://gitlab.torproject.org/ahf/margot/-/tree/ahf/tls-ciphers-scanner),
writes `cipher_suites.csv`. The header is:

```
nickname;rsa_id;ed25519_id;weight_status;weight;connected;address;cipher_suite;key_exchange_group
```

`weight` is `measured;<n>` or `unmeasured;<n>`, so the semicolon is part of
that value and the line has nine fields. A relay whose handshake did not
complete is still a row: `connected` is false and the cipher and group are
empty.

## What is published

[ahf.me/tor-tls-pqc/](https://ahf.me/tor-tls-pqc/) is an index of dated pages.
Checked pages (2026-02-26, 2026-03-01, 2026-06-18) are HTML tables with
columns Nickname, Fingerprint, Cipher Suite, and Group (`id=tor_pqc_tls_table`).
Those directories do not publish a JSON or CSV file. The date in the page
URL is the scan time; the HTML has no clock time.

`--tls-pqc-url` accepts the index (default; the newest dated link is used),
one dated scan page, or a Margot CSV. The parsed document is cached like the
other non-Onionoo documents (`allium/data/cache/tls_pqc.json`, 24 hours).

## How a relay is counted

- The scan recorded `X25519MLKEM768`: the latest scan saw it.
- The scan recorded a different group: the latest scan did not see it.
- The fingerprint is in the scan and the group is empty: no negotiated group.
- The fingerprint is absent: "not in this scan".

Directory-authority counts join the Authority flag on the current consensus
to that scan. The denominator is however many authorities are in the
consensus, not a fixed 9.
