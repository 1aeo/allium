#!/usr/bin/env python3
"""
Test upstream resolver data from exitdnshealth.1aeo.com: per-exit results[].resolver
and network-wide metadata.resolvers (exitmap-dns-health-deploy scripts/resolver_stats.py).

Covers parsing (present, absent, malformed, partial), relay attachment,
dashboard metrics and their formatted strings.
"""

import copy

import pytest

from allium.lib.exit_dns_health import (
    RESOLVER_CATEGORIES,
    attach_exit_dns_health_to_relays,
    build_exit_dns_health_map,
    calculate_exit_dns_health_metrics,
    parse_resolver_summary,
)
from allium.lib.network_health import preformat_network_health_template_strings


RESOLVERS = {
    "version": 1, "source": "cloudflare-dns-analytics-sampled",
    "window": {"start": "2026-10-12T07:00:00Z", "end": "2026-10-12T07:35:00Z"},
    "rows": 3057, "est_queries": 30570, "half_life_hours": 84, "thresholds": {"seen": 5, "label": 25},
    "weighted": True, "exits_total": 2674, "exits_covered": 2670, "exits_labelled": 2608, "exits_using_public": 512,
    "public_share_pct": {"google": 10.5, "cloudflare": 7.99, "quad9": 2.0, "opendns": 0.0, "ffmuc": 1.12, "all": 21.61},
    "share_pct": {"google": 10.5, "cloudflare": 7.99, "quad9": 2.0, "opendns": 0.0, "ffmuc": 1.12,
                  "local": 66.69, "other": 11.7, "unknown": 0.0},
    "classification": {"google": "https://www.gstatic.com/ipranges/publicdns.json"},
}


def _report(results, resolvers=RESOLVERS):
    metadata = {"timestamp": "2026-10-12T07:27:12Z", "dns_success_rate_percent": 99.0}
    if resolvers is not None:
        metadata["resolvers"] = copy.deepcopy(resolvers)
    return {"metadata": metadata, "results": results}


def _result(fp, resolver=None, status="success"):
    result = {"exit_fingerprint": fp, "status": status, "timing": {"total_ms": 1000}}
    if resolver is not None:
        result["resolver"] = resolver
    return result


def _resolver_of(resolver):
    """Parse one resolver block through the map builder."""
    return build_exit_dns_health_map(_report([_result("AAA", resolver)]))["AAA"]["resolver"]


def _attach(report, relays):
    attach_exit_dns_health_to_relays(relays, build_exit_dns_health_map(report))
    return {r["fingerprint"]: r for r in relays}


# ---------------------------------------------------------------------------
# build_exit_dns_health_map: results[].resolver
# ---------------------------------------------------------------------------

def test_resolver_present():
    resolver = _resolver_of({"primary": "google", "public": True, "queries": {"local": 4.2, "google": 61.3}})
    assert resolver == {"primary": "google", "public": True, "queries": {"google": 61.3, "local": 4.2}}
    assert list(resolver["queries"]) == ["google", "local"]  # largest first


def test_resolver_cold_start():
    resolver = _resolver_of({"primary": None, "public": None, "queries": {"other": 3.5}})
    assert resolver == {"primary": None, "public": None, "queries": {"other": 3.5}}


def test_resolver_local_is_not_public():
    resolver = _resolver_of({"primary": "local", "public": False, "queries": {"local": 40}})
    assert resolver["primary"] == "local"
    assert resolver["public"] is False


def test_resolver_absent():
    assert _resolver_of(None) is None


@pytest.mark.parametrize("resolver", ["google", ["google"], 42, True])
def test_resolver_not_a_dict(resolver):
    assert _resolver_of(resolver) is None


def test_resolver_bad_query_values_dropped():
    resolver = _resolver_of({"primary": "google", "public": True, "queries": {
        "google": 30, "cloudflare": "12", "quad9": True, "opendns": -1, "ffmuc": float("nan"),
        "local": float("inf"), "other": None, "unknown": 10 ** 400,
    }})
    assert resolver["queries"] == {"google": 30.0}


@pytest.mark.parametrize("queries", [None, "google=3", ["google", 3], 7])
def test_resolver_queries_not_a_dict(queries):
    resolver = _resolver_of({"primary": "google", "public": True, "queries": queries})
    assert resolver == {"primary": "google", "public": True, "queries": {}}


def test_resolver_unknown_category_counts_as_other():
    resolver = _resolver_of({"primary": "nextdns", "public": True,
                             "queries": {"nextdns": 20.5, "other": 1.25, "<b>x</b>": 3}})
    assert resolver["primary"] == "other"
    assert resolver["public"] is True
    assert resolver["queries"] == {"other": 24.75}
    assert set(resolver["queries"]) <= set(RESOLVER_CATEGORIES)


@pytest.mark.parametrize(("primary", "public", "expected"), [
    ({"x": 1}, True, (None, None)),       # not a string
    (None, True, (None, None)),           # no primary yet: public is undefined
    ("unknown", False, ("unknown", None)),
    ("google", "yes", ("google", None)),  # public must be a bool
    ("quad9", 1, ("quad9", None)),
])
def test_resolver_primary_and_public_validated(primary, public, expected):
    resolver = _resolver_of({"primary": primary, "public": public, "queries": {"google": 30}})
    assert (resolver["primary"], resolver["public"]) == expected


def test_resolver_missing_keys():
    assert _resolver_of({}) == {"primary": None, "public": None, "queries": {}}


# ---------------------------------------------------------------------------
# attach_exit_dns_health_to_relays: relay fields
# ---------------------------------------------------------------------------

def test_attach_resolver_fields():
    report = _report([
        _result("PUB", {"primary": "google", "public": True, "queries": {"google": 61.3, "local": 4.2}}),
        _result("LOC", {"primary": "local", "public": False, "queries": {"local": 40.0}}),
        _result("NEW", {"primary": None, "public": None, "queries": {"other": 3.5}}),
        _result("NONE"),
        _result("FAIL", {"primary": "cloudflare", "public": True, "queries": {"cloudflare": 26}}, status="dns_fail"),
    ])
    relays = _attach(report, [{"fingerprint": fp, "flags": ["Exit"]}
                              for fp in ("PUB", "LOC", "NEW", "NONE", "FAIL", "UNTESTED")]
                     + [{"fingerprint": "GUARD", "flags": ["Guard"]}])

    def fields(fp):
        r = relays[fp]
        return (r["exit_dns_health_resolver_primary"], r["exit_dns_health_resolver_public"],
                r["exit_dns_health_resolver_queries"])

    assert fields("PUB") == ("google", True, {"google": 61.3, "local": 4.2})
    assert fields("LOC") == ("local", False, {"local": 40.0})
    assert fields("NEW") == (None, None, {"other": 3.5})
    # In a report with resolver data, an exit without any has no queries yet
    assert fields("NONE") == (None, None, {})
    assert fields("FAIL") == ("cloudflare", True, {"cloudflare": 26.0})
    assert fields("UNTESTED") == (None, None, None)
    assert "exit_dns_health_resolver_queries" not in relays["GUARD"]


def test_attach_without_resolver_data():
    """Older reports and failed resolver runs: no resolver row anywhere."""
    relays = _attach(_report([_result("AAA")], resolvers=None), [{"fingerprint": "AAA", "flags": ["Exit"]}])
    assert relays["AAA"]["exit_dns_health_status"] == "success"
    assert relays["AAA"]["exit_dns_health_resolver_primary"] is None
    assert relays["AAA"]["exit_dns_health_resolver_public"] is None
    assert relays["AAA"]["exit_dns_health_resolver_queries"] is None


def test_attach_health_entry_without_resolver_key():
    """Entries built elsewhere (older shape) without a 'resolver' key still attach."""
    entry = build_exit_dns_health_map(_report([_result("AAA")]))["AAA"]
    del entry["resolver"]
    relays = [{"fingerprint": "AAA", "flags": ["Exit"]}]
    attach_exit_dns_health_to_relays(relays, {"AAA": entry})
    assert relays[0]["exit_dns_health_resolver_queries"] is None


def test_attach_queries_not_shared_between_relays():
    relays = _attach(_report([_result("A1", {"primary": "google", "public": True, "queries": {"google": 30}}),
                              _result("A2"), _result("A3")]),
                     [{"fingerprint": fp, "flags": ["Exit"]} for fp in ("A1", "A2", "A3")])
    relays["A2"]["exit_dns_health_resolver_queries"]["google"] = 1
    assert relays["A3"]["exit_dns_health_resolver_queries"] == {}


# ---------------------------------------------------------------------------
# parse_resolver_summary / calculate_exit_dns_health_metrics: metadata.resolvers
# ---------------------------------------------------------------------------

def test_summary_present():
    summary = parse_resolver_summary({"resolvers": RESOLVERS})
    assert summary["public_share_pct"] == {"google": 10.5, "cloudflare": 7.99, "quad9": 2.0, "opendns": 0.0,
                                           "ffmuc": 1.12, "all": 21.61}
    assert summary["share_pct"]["local"] == 66.69
    assert (summary["exits_total"], summary["exits_covered"], summary["exits_labelled"],
            summary["exits_using_public"]) == (2674, 2670, 2608, 512)
    assert summary["weighted"] is True


@pytest.mark.parametrize("metadata", [
    None, "x", {}, {"resolvers": None}, {"resolvers": "x"}, {"resolvers": []}, {"resolvers": {}},
    {"resolvers": {"version": 1, "public_share_pct": "x", "share_pct": [1, 2], "exits_total": "2674"}},
])
def test_summary_absent_or_unusable(metadata):
    assert parse_resolver_summary(metadata) is None


def test_summary_partial_and_malformed_values():
    summary = parse_resolver_summary({"resolvers": {
        "public_share_pct": {"google": 12.5, "cloudflare": "8", "quad9": None, "all": 100.4},
        "exits_covered": 10, "exits_total": True, "exits_labelled": 2.0, "exits_using_public": 2.5,
        "weighted": "yes",
    }})
    assert summary["public_share_pct"] == {"google": 12.5, "cloudflare": None, "quad9": None, "opendns": None,
                                           "ffmuc": None, "all": 100.0}
    assert summary["share_pct"] == {c: None for c in RESOLVER_CATEGORIES}
    assert (summary["exits_total"], summary["exits_covered"], summary["exits_labelled"],
            summary["exits_using_public"]) == (None, 10, 2, None)
    assert summary["weighted"] is None


def test_metrics_resolvers_present():
    m = calculate_exit_dns_health_metrics(_report([]))
    assert m["exit_dns_health_resolvers_available"] is True
    assert m["exit_dns_health_resolver_google_percentage"] == 10.5
    assert m["exit_dns_health_resolver_ffmuc_percentage"] == 1.12
    assert m["exit_dns_health_resolver_public_percentage"] == 21.61
    assert m["exit_dns_health_resolver_local_percentage"] == 66.69
    assert m["exit_dns_health_resolver_other_percentage"] == 11.7
    assert m["exit_dns_health_resolver_unknown_percentage"] == 0.0
    assert m["exit_dns_health_resolver_exits_covered"] == 2670
    assert m["exit_dns_health_resolver_exits_using_public"] == 512
    assert m["exit_dns_health_resolver_weighted"] is True


@pytest.mark.parametrize("data", [None, _report([], resolvers=None), _report([], resolvers={"version": 1})])
def test_metrics_resolvers_not_available(data):
    m = calculate_exit_dns_health_metrics(data)
    assert m["exit_dns_health_resolvers_available"] is False
    resolver_values = {k: v for k, v in m.items()
                       if k.startswith("exit_dns_health_resolver_")}
    assert resolver_values  # the keys exist for templates ...
    assert all(v is None for v in resolver_values.values())  # ... but never as zeros


def test_metrics_existing_keys_unchanged_by_resolvers():
    with_resolvers = calculate_exit_dns_health_metrics(_report([]))
    without = calculate_exit_dns_health_metrics(_report([], resolvers=None))
    new_keys = {k for k in with_resolvers if k.startswith("exit_dns_health_resolver")}
    assert {k: v for k, v in with_resolvers.items() if k not in new_keys} == \
        {k: v for k, v in without.items() if k not in new_keys}


def test_formatted_strings():
    m = calculate_exit_dns_health_metrics(_report([]))
    preformat_network_health_template_strings(m)
    assert m["exit_dns_health_resolver_google_percentage_formatted"] == "10.5%"
    assert m["exit_dns_health_resolver_public_percentage_formatted"] == "21.6%"
    assert m["exit_dns_health_resolver_local_percentage_formatted"] == "66.7%"
    assert m["exit_dns_health_resolver_exits_total_formatted"] == "2,674"
    assert m["exit_dns_health_resolver_exits_covered_formatted"] == "2,670"
    assert m["exit_dns_health_resolver_exits_labelled_formatted"] == "2,608"
    assert m["exit_dns_health_resolver_exits_using_public_formatted"] == "512"


def test_formatted_strings_not_available():
    m = calculate_exit_dns_health_metrics(_report([], resolvers=None))
    preformat_network_health_template_strings(m)
    assert m["exit_dns_health_resolver_google_percentage_formatted"] == "n/a"
    assert m["exit_dns_health_resolver_exits_covered_formatted"] == "n/a"
    assert m["exit_dns_health_tested_formatted"] == "0"  # existing keys still format as before
