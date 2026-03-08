#!/usr/bin/env python3

from allium.lib.page_writer import (
    CONTACT_SORT_MODES,
    CONTACT_SORT_FILE_MAP,
    _sort_contact_relays,
    _sort_contact_section_entries,
)


def _relay(
    fingerprint,
    nickname,
    running,
    observed_bandwidth,
    total_data_5y,
    uptime_6m,
    flag_uptime_6m,
    ipv4,
    ipv6,
    flags,
    dns_status,
    family_support_type,
    country,
    as_number,
    as_name,
    platform,
    first_seen,
    last_restarted,
    last_seen,
):
    return {
        "fingerprint": fingerprint,
        "nickname": nickname,
        "running": running,
        "observed_bandwidth": observed_bandwidth,
        "total_data": {
            "1_month": 0,
            "6_months": 0,
            "1_year": 0,
            "5_years": total_data_5y,
        },
        "uptime_percentages": {
            "1_month": uptime_6m - 5,
            "6_months": uptime_6m,
            "1_year": uptime_6m - 10,
            "5_years": uptime_6m - 15,
        },
        "_flag_uptime_data": {
            "Exit": {
                "6_months": {"uptime": flag_uptime_6m, "data_points": 30},
            }
        } if flag_uptime_6m >= 0 else {},
        "or_addresses": [f"{ipv4}:9001", f"[{ipv6}]:9001"] if ipv6 else [f"{ipv4}:9001"],
        "flags": flags,
        "exit_dns_health_status": dns_status,
        "family_support_type": family_support_type,
        "effective_family": ["A", "B", "C"] if family_support_type != "none" else [],
        "country": country,
        "country_name": country,
        "as": as_number,
        "as_name": as_name,
        "platform": platform,
        "first_seen": first_seen,
        "last_restarted": last_restarted,
        "last_seen": last_seen,
    }


def _sample_relays():
    return [
        _relay(
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "alpha",
            True,
            100,
            500,
            80,
            70,
            "2.2.2.2",
            "2001:db8::2",
            ["Guard", "Running"],
            "fail",
            "my_family",
            "US",
            "AS20",
            "ZetaNet",
            "Linux",
            "2025-01-01 00:00:00",
            "2026-03-01 00:00:00",
            "2026-03-08 00:00:00",
        ),
        _relay(
            "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "beta",
            True,
            300,
            900,
            90,
            95,
            "1.1.1.1",
            "2001:db8::1",
            ["Exit", "Running"],
            "success",
            "both",
            "DE",
            "AS10",
            "AlphaNet",
            "FreeBSD",
            "2026-01-01 00:00:00",
            "2026-03-07 00:00:00",
            "2026-03-08 00:00:00",
        ),
        _relay(
            "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
            "gamma",
            False,
            200,
            100,
            50,
            -1,
            "9.9.9.9",
            "",
            ["Running"],
            "untested",
            "none",
            "FR",
            "",
            "",
            "Windows",
            "2024-01-01 00:00:00",
            None,
            "2026-03-08 05:00:00",
        ),
    ]


def test_contact_sort_modes_have_expected_mapping():
    assert "bandwidth" in CONTACT_SORT_MODES
    assert CONTACT_SORT_FILE_MAP["bandwidth"] == "index.html"
    assert "by-bandwidth.html" not in CONTACT_SORT_FILE_MAP.values()
    assert len(CONTACT_SORT_MODES) == 18


def test_contact_sorting_produces_deterministic_order_for_all_modes():
    relays = _sample_relays()

    for mode in CONTACT_SORT_MODES:
        sorted_relays = _sort_contact_relays(relays, mode)
        fingerprints = [relay["fingerprint"] for relay in sorted_relays]
        assert sorted(fingerprints) == sorted([relay["fingerprint"] for relay in relays]), mode


def test_selected_sort_mode_expected_first_rows():
    relays = _sample_relays()

    assert _sort_contact_relays(relays, "bandwidth")[0]["nickname"] == "beta"
    assert _sort_contact_relays(relays, "total_data")[0]["nickname"] == "beta"
    assert _sort_contact_relays(relays, "nickname")[0]["nickname"] == "alpha"
    assert _sort_contact_relays(relays, "uptime")[0]["nickname"] == "alpha"  # longest running uptime first
    assert _sort_contact_relays(relays, "uptime_percentage")[0]["nickname"] == "beta"
    assert _sort_contact_relays(relays, "flag_uptime")[0]["nickname"] == "beta"
    assert _sort_contact_relays(relays, "ipv4")[0]["nickname"] == "beta"
    assert _sort_contact_relays(relays, "dns")[0]["nickname"] == "beta"
    assert _sort_contact_relays(relays, "family")[0]["nickname"] == "beta"
    assert _sort_contact_relays(relays, "first_seen")[0]["nickname"] == "beta"  # newest first
    assert _sort_contact_relays(relays, "last_restarted")[0]["nickname"] == "beta"  # newest first
    assert _sort_contact_relays(relays, "ipv6")[0]["nickname"] == "beta"


def test_contact_sort_tie_breaker_uses_fingerprint():
    relay_1 = _relay(
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "same",
        True,
        100,
        10,
        50,
        40,
        "1.1.1.1",
        "",
        ["Running"],
        "success",
        "none",
        "US",
        "AS1",
        "Name",
        "Linux",
        "2025-01-01 00:00:00",
        "2026-03-01 00:00:00",
        "2026-03-08 00:00:00",
    )
    relay_2 = _relay(
        "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        "same",
        True,
        100,
        10,
        50,
        40,
        "1.1.1.1",
        "",
        ["Running"],
        "success",
        "none",
        "US",
        "AS1",
        "Name",
        "Linux",
        "2025-01-01 00:00:00",
        "2026-03-01 00:00:00",
        "2026-03-08 00:00:00",
    )

    sorted_relays = _sort_contact_relays([relay_2, relay_1], "nickname")
    assert [relay["fingerprint"] for relay in sorted_relays] == [
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    ]


def test_section_wrapper_sorting_uses_embedded_relay():
    relays = _sample_relays()
    wrapped = [{"relay": relay} for relay in relays]
    sorted_wrapped = _sort_contact_section_entries(wrapped, "bandwidth")
    assert sorted_wrapped[0]["relay"]["nickname"] == "beta"
