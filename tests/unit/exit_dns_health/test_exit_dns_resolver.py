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
    resolver_share_tenths,
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
    """Report with the given results; resolvers=None leaves out metadata.resolvers."""
    metadata = {"timestamp": "2026-10-12T07:27:12Z", "dns_success_rate_percent": 99.0}
    if resolvers is not None:
        metadata["resolvers"] = copy.deepcopy(resolvers)
    return {"metadata": metadata, "results": results}


def _result(fp, resolver=None, status="success"):
    """One results[] entry, with a resolver block when given."""
    result = {"exit_fingerprint": fp, "status": status, "timing": {"total_ms": 1000}}
    if resolver is not None:
        result["resolver"] = resolver
    return result


def _resolver_of(resolver):
    """Parse one resolver block through the map builder."""
    return build_exit_dns_health_map(_report([_result("AAA", resolver)]))["AAA"]["resolver"]


def _attach(report, relays):
    """Attach the report's DNS health to relays and index them by fingerprint."""
    attach_exit_dns_health_to_relays(relays, build_exit_dns_health_map(report))
    return {r["fingerprint"]: r for r in relays}


# ---------------------------------------------------------------------------
# build_exit_dns_health_map: results[].resolver
# ---------------------------------------------------------------------------

def test_resolver_present():
    """A labelled block keeps primary, public and its queries, largest first."""
    resolver = _resolver_of({"primary": "google", "public": True, "queries": {"local": 4.2, "google": 61.3}})
    assert resolver == {"primary": "google", "public": True, "queries": {"google": 61.3, "local": 4.2}}
    assert list(resolver["queries"]) == ["google", "local"]  # largest first


def test_resolver_cold_start():
    """Before 25 estimated queries upstream has no primary; the counts still come through."""
    resolver = _resolver_of({"primary": None, "public": None, "queries": {"other": 3.5}})
    assert resolver == {"primary": None, "public": None, "queries": {"other": 3.5}}


def test_resolver_local_is_not_public():
    """A local primary is labelled but not public."""
    resolver = _resolver_of({"primary": "local", "public": False, "queries": {"local": 40}})
    assert resolver["primary"] == "local"
    assert resolver["public"] is False


def test_resolver_absent():
    """Exits without a resolver block parse to None."""
    assert _resolver_of(None) is None


@pytest.mark.parametrize("resolver", ["google", ["google"], 42, True])
def test_resolver_not_a_dict(resolver):
    """A resolver value that is not a dict is ignored."""
    assert _resolver_of(resolver) is None


def test_resolver_bad_query_values_dropped():
    """Strings, bools, negatives, NaN, inf, None and huge ints are not counts."""
    resolver = _resolver_of({"primary": "google", "public": True, "queries": {
        "google": 30, "cloudflare": "12", "quad9": True, "opendns": -1, "ffmuc": float("nan"),
        "local": float("inf"), "other": None, "unknown": 10 ** 400,
    }})
    assert resolver["queries"] == {"google": 30.0}


@pytest.mark.parametrize("queries", [None, "google=3", ["google", 3], 7])
def test_resolver_queries_not_a_dict(queries):
    """A queries value that is not a dict leaves no counts."""
    resolver = _resolver_of({"primary": "google", "public": True, "queries": queries})
    assert resolver == {"primary": "google", "public": True, "queries": {}}


def test_resolver_unknown_category_counts_as_other():
    """Categories this version does not know fold into 'other'."""
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
    """primary must be a string category; public must be a bool and needs a known primary."""
    resolver = _resolver_of({"primary": primary, "public": public, "queries": {"google": 30}})
    assert (resolver["primary"], resolver["public"]) == expected


def test_resolver_missing_keys():
    """An empty block parses to no primary and no counts."""
    assert _resolver_of({}) == {"primary": None, "public": None, "queries": {}}


# ---------------------------------------------------------------------------
# attach_exit_dns_health_to_relays: relay fields
# ---------------------------------------------------------------------------

def test_attach_resolver_fields():
    """Each kind of exit gets the documented primary/public/queries values."""
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
        """(primary, public, queries) of the relay with fingerprint fp."""
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
    """Exits without data each get their own empty dict."""
    relays = _attach(_report([_result("A1", {"primary": "google", "public": True, "queries": {"google": 30}}),
                              _result("A2"), _result("A3")]),
                     [{"fingerprint": fp, "flags": ["Exit"]} for fp in ("A1", "A2", "A3")])
    relays["A2"]["exit_dns_health_resolver_queries"]["google"] = 1
    assert relays["A3"]["exit_dns_health_resolver_queries"] == {}


# ---------------------------------------------------------------------------
# parse_resolver_summary / calculate_exit_dns_health_metrics: metadata.resolvers
# ---------------------------------------------------------------------------

def test_summary_present():
    """A complete block parses to its shares, counts and weighting."""
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
    """No block, or one without any usable value, parses to None."""
    assert parse_resolver_summary(metadata) is None


def test_summary_partial_and_malformed_values():
    """Bad values become None, shares are capped at 100, good ones are kept."""
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


def test_summary_cold_start_shares_are_not_zeros():
    """Before any exit is covered, upstream publishes 0.0 placeholders for every share."""
    cold = dict(RESOLVERS, exits_covered=0, exits_labelled=0, exits_using_public=0,
                public_share_pct=dict.fromkeys(RESOLVERS["public_share_pct"], 0.0),
                share_pct=dict.fromkeys(RESOLVERS["share_pct"], 0.0))
    summary = parse_resolver_summary({"resolvers": cold})
    assert set(summary["public_share_pct"].values()) == {None}
    assert set(summary["share_pct"].values()) == {None}
    assert (summary["exits_total"], summary["exits_covered"], summary["exits_using_public"]) == (2674, 0, 0)

    m = calculate_exit_dns_health_metrics(_report([], resolvers=cold))
    preformat_network_health_template_strings(m)
    assert m["exit_dns_health_resolvers_available"] is True
    assert m["exit_dns_health_resolver_public_percentage_formatted"] == "n/a"
    assert m["exit_dns_health_resolver_local_percentage_formatted"] == "n/a"
    assert m["exit_dns_health_resolver_exits_covered_formatted"] == "0"


def test_metrics_resolvers_present():
    """Dashboard keys carry the block's shares and counts."""
    m = calculate_exit_dns_health_metrics(_report([]))
    assert m["exit_dns_health_resolvers_available"] is True
    assert m["exit_dns_health_resolver_google_percentage"] == 10.5
    assert m["exit_dns_health_resolver_ffmuc_percentage"] == 1.12
    assert m["exit_dns_health_resolver_public_percentage"] == 21.61
    assert m["exit_dns_health_resolver_local_percentage"] == 66.69
    assert m["exit_dns_health_resolver_local_24_percentage"] is None  # version 1 has no tiers
    assert m["exit_dns_health_resolver_other_percentage"] == 11.7
    assert m["exit_dns_health_resolver_unknown_percentage"] == 0.0
    assert m["exit_dns_health_resolver_exits_covered"] == 2670
    assert m["exit_dns_health_resolver_exits_using_public"] == 512
    assert m["exit_dns_health_resolver_weighted"] is True


@pytest.mark.parametrize("data", [None, _report([], resolvers=None), _report([], resolvers={"version": 1})])
def test_metrics_resolvers_not_available(data):
    """Without a usable block every resolver key is None and availability is False."""
    m = calculate_exit_dns_health_metrics(data)
    assert m["exit_dns_health_resolvers_available"] is False
    resolver_values = {k: v for k, v in m.items()
                       if k.startswith("exit_dns_health_resolver_")}
    assert resolver_values  # the keys exist for templates ...
    assert all(v is None for v in resolver_values.values())  # ... but never as zeros


def test_metrics_existing_keys_unchanged_by_resolvers():
    """Resolver data changes none of the existing dashboard keys."""
    with_resolvers = calculate_exit_dns_health_metrics(_report([]))
    without = calculate_exit_dns_health_metrics(_report([], resolvers=None))
    new_keys = {k for k in with_resolvers if k.startswith("exit_dns_health_resolver")}
    assert {k: v for k, v in with_resolvers.items() if k not in new_keys} == \
        {k: v for k, v in without.items() if k not in new_keys}


def test_metrics_version2_local_is_the_sum_of_tiers():
    """Version 2's local percentage is local_24 + local_22 + local_as + local_operator."""
    resolvers = copy.deepcopy(RESOLVERS)
    resolvers["version"] = 2
    resolvers["share_pct"] = {
        "google": 10.83, "cloudflare": 8.04, "quad9": 1.88, "opendns": 0.0, "ffmuc": 1.02,
        "local_24": 55.58, "local_22": 1.54, "local_as": 10.92, "local_operator": 7.59,
        "other": 2.82, "unknown": 0.0,
    }
    summary = parse_resolver_summary({"resolvers": resolvers})
    assert summary["share_pct"]["local"] is None
    assert summary["share_pct"]["local_24"] == 55.58
    assert summary["share_pct"]["local_operator"] == 7.59
    m = calculate_exit_dns_health_metrics(_report([], resolvers=resolvers))
    assert m["exit_dns_health_resolver_local_percentage"] == 75.63
    assert m["exit_dns_health_resolver_local_24_percentage"] == 55.58
    assert m["exit_dns_health_resolver_local_22_percentage"] == 1.54
    assert m["exit_dns_health_resolver_local_as_percentage"] == 10.92
    assert m["exit_dns_health_resolver_local_operator_percentage"] == 7.59
    preformat_network_health_template_strings(m)
    assert m["exit_dns_health_resolver_local_percentage_formatted"] == "75.6%"
    assert m["exit_dns_health_resolver_local_operator_percentage_formatted"] == "7.6%"


def test_partial_version2_tiers_are_not_summed():
    """A version-2 report that omits a tier does not publish the rest as the Local total."""
    resolvers = copy.deepcopy(RESOLVERS)
    resolvers["version"] = 2
    resolvers["share_pct"] = {"google": 10.0, "local_24": 55.0, "other": 35.0, "unknown": 0.0}
    metrics = calculate_exit_dns_health_metrics(_report([], resolvers=resolvers))
    assert metrics["exit_dns_health_resolver_local_24_percentage"] == 55.0
    assert metrics["exit_dns_health_resolver_local_operator_percentage"] is None
    assert metrics["exit_dns_health_resolver_local_percentage"] is None


def test_version2_tier_primary_is_not_public():
    """A local_24 or local_operator primary stays that category and is not public."""
    tier = _resolver_of({"primary": "local_24", "public": False,
                         "queries": {"local_24": 40, "local_operator": 8}})
    assert tier == {"primary": "local_24", "public": False, "queries": {"local_24": 40.0, "local_operator": 8.0}}
    operator = _resolver_of({"primary": "local_operator", "public": False, "queries": {"local_operator": 12}})
    assert operator["primary"] == "local_operator"
    assert operator["public"] is False


def test_formatted_strings():
    """Shares format as percentages and counts with thousands separators."""
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
    """Missing values format as n/a."""
    m = calculate_exit_dns_health_metrics(_report([], resolvers=None))
    preformat_network_health_template_strings(m)
    assert m["exit_dns_health_resolver_google_percentage_formatted"] == "n/a"
    assert m["exit_dns_health_resolver_exits_covered_formatted"] == "n/a"
    assert m["exit_dns_health_tested_formatted"] == "0"  # existing keys still format as before


# Version-2 shares from a live report: rounded one by one, All Public + Local + Other + Unknown
# shows 22.2 + 74.1 + 3.6 + 0.0 = 99.9%.
LIVE_V2_SHARE = {
    "google": 11.0, "cloudflare": 8.09, "quad9": 1.94, "opendns": 0.0, "ffmuc": 1.19,
    "local_24": 61.07, "local_22": 6.88, "local_as": 1.85, "local_operator": 4.34, "other": 3.64, "unknown": 0.0,
}


def _v2_resolvers(share):
    """A version-2 metadata.resolvers block with the given share_pct."""
    resolvers = copy.deepcopy(RESOLVERS)
    resolvers["version"] = 2
    resolvers["share_pct"] = dict(share)
    providers = {p: share[p] for p in ("google", "cloudflare", "quad9", "opendns", "ffmuc")}
    resolvers["public_share_pct"] = dict(providers, all=round(sum(providers.values()), 2))
    return resolvers


def _formatted_shares(resolvers):
    """{category: formatted dashboard share} for a resolvers block."""
    m = calculate_exit_dns_health_metrics(_report([], resolvers=resolvers))
    preformat_network_health_template_strings(m)
    names = ("google", "cloudflare", "quad9", "opendns", "ffmuc", "public", "local", "local_24", "local_22",
             "local_as", "local_operator", "other", "unknown")
    return m, {n: m[f"exit_dns_health_resolver_{n}_percentage_formatted"] for n in names}


def _pct(text):
    """Tenths of a percent from a formatted share such as '22.2%'."""
    return round(float(text.rstrip("%")) * 10)


def test_formatted_shares_add_up_to_100():
    """The four categories show exactly 100.0%, and providers and tiers add up to their totals."""
    m, shown = _formatted_shares(_v2_resolvers(LIVE_V2_SHARE))
    assert (shown["public"], shown["local"], shown["other"], shown["unknown"]) == ("22.2%", "74.2%", "3.6%", "0.0%")
    assert sum(_pct(shown[c]) for c in ("public", "local", "other", "unknown")) == 1000
    assert sum(_pct(shown[p]) for p in ("google", "cloudflare", "quad9", "opendns", "ffmuc")) == _pct(shown["public"])
    assert sum(_pct(shown[t]) for t in ("local_24", "local_22", "local_as", "local_operator")) == _pct(shown["local"])
    # Only the display is rounded together: raw values (Prometheus, templates' raw keys) are unchanged
    assert m["exit_dns_health_resolver_local_percentage"] == 74.14
    assert m["exit_dns_health_resolver_public_percentage"] == 22.22


def test_share_tenths_match_the_exitdnshealth_dashboard():
    """Same rounding as exitdnshealth.1aeo.com, so both sites show the same numbers."""
    key = "exit_dns_health_resolver_{}_percentage".format
    m = calculate_exit_dns_health_metrics(_report([], resolvers=_v2_resolvers(LIVE_V2_SHARE)))
    tenths = resolver_share_tenths(m)
    # Expected values computed by the exitdnshealth dashboard (public/app.js roundSharesToTotal)
    assert {k: tenths[key(k)] for k in LIVE_V2_SHARE} == {
        "google": 110, "cloudflare": 81, "quad9": 19, "opendns": 0, "ffmuc": 12, "local_24": 611, "local_22": 69,
        "local_as": 19, "local_operator": 43, "other": 36, "unknown": 0}
    assert (tenths[key("public")], tenths[key("local")]) == (222, 742)
    v1 = resolver_share_tenths(calculate_exit_dns_health_metrics(_report([])))
    assert {k: v1[key(k)] for k in RESOLVERS["share_pct"]} == {
        "google": 105, "cloudflare": 80, "quad9": 20, "opendns": 0, "ffmuc": 11, "local": 667, "other": 117,
        "unknown": 0}


@pytest.mark.parametrize("drop, change, other", [
    ("local_operator", {}, "3.6%"),    # a version-2 tier is missing: no Local total
    ("other", {}, "n/a"),              # a category is missing
    (None, {"other": 50.0}, "50.0%"),  # shares far from 100% (malformed report)
])
def test_share_tenths_fall_back_to_rounding_each_share(drop, change, other):
    """Without a complete set of shares that totals about 100%, each share is rounded on its own."""
    share = {k: v for k, v in dict(LIVE_V2_SHARE, **change).items() if k != drop}
    m, shown = _formatted_shares(_v2_resolvers(share))
    assert resolver_share_tenths(m) is None
    assert shown["local_24"] == "61.1%"
    assert shown["other"] == other
