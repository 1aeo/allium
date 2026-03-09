#!/usr/bin/env python3

from allium.lib.contact_sorting import (
    CONTACT_SORT_MODES,
    CONTACT_SORT_FILE_MAP,
    sort_contact_relays,
    sort_contact_section_entries,
    contact_relay_count,
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
        sorted_relays = sort_contact_relays(relays, mode)
        fingerprints = [relay["fingerprint"] for relay in sorted_relays]
        assert sorted(fingerprints) == sorted([relay["fingerprint"] for relay in relays]), mode


def test_selected_sort_mode_expected_first_rows():
    relays = _sample_relays()

    assert sort_contact_relays(relays, "bandwidth")[0]["nickname"] == "beta"
    assert sort_contact_relays(relays, "total_data")[0]["nickname"] == "beta"
    assert sort_contact_relays(relays, "nickname")[0]["nickname"] == "alpha"
    assert sort_contact_relays(relays, "uptime")[0]["nickname"] == "alpha"  # longest running uptime first
    assert sort_contact_relays(relays, "uptime_percentage")[0]["nickname"] == "beta"
    assert sort_contact_relays(relays, "flag_uptime")[0]["nickname"] == "beta"
    assert sort_contact_relays(relays, "ipv4")[0]["nickname"] == "beta"
    assert sort_contact_relays(relays, "dns")[0]["nickname"] == "beta"
    assert sort_contact_relays(relays, "family")[0]["nickname"] == "beta"
    assert sort_contact_relays(relays, "first_seen")[0]["nickname"] == "beta"  # newest first
    assert sort_contact_relays(relays, "last_restarted")[0]["nickname"] == "beta"  # newest first
    assert sort_contact_relays(relays, "ipv6")[0]["nickname"] == "beta"


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

    sorted_relays = sort_contact_relays([relay_2, relay_1], "nickname")
    assert [relay["fingerprint"] for relay in sorted_relays] == [
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    ]


def test_section_wrapper_sorting_uses_embedded_relay():
    relays = _sample_relays()
    wrapped = [{"relay": relay} for relay in relays]
    sorted_wrapped = sort_contact_section_entries(wrapped, "bandwidth")
    assert sorted_wrapped[0]["relay"]["nickname"] == "beta"


# =============================================================================
# NUMERIC IP SORT ORDERING (bug fix validation)
# =============================================================================

def test_ipv4_sort_is_numeric_not_lexicographic():
    """IPv4 addresses must sort by numeric value, not string comparison.

    Lexicographic: '1.1.1.1' < '192.168.1.1' < '9.9.9.9' (WRONG)
    Numeric:       '1.1.1.1' < '2.2.2.2' < '9.9.9.9' < '192.168.1.1' (CORRECT)
    """
    relays = [
        _relay("FP_192", "relay_192", True, 100, 0, 50, -1, "192.168.1.1", "", ["Running"], "success", "none", "US", "", "", "Linux", "2025-01-01 00:00:00", "2026-03-01 00:00:00", "2026-03-08 00:00:00"),
        _relay("FP_009", "relay_9", True, 100, 0, 50, -1, "9.9.9.9", "", ["Running"], "success", "none", "US", "", "", "Linux", "2025-01-01 00:00:00", "2026-03-01 00:00:00", "2026-03-08 00:00:00"),
        _relay("FP_001", "relay_1", True, 100, 0, 50, -1, "1.1.1.1", "", ["Running"], "success", "none", "US", "", "", "Linux", "2025-01-01 00:00:00", "2026-03-01 00:00:00", "2026-03-08 00:00:00"),
        _relay("FP_002", "relay_2", True, 100, 0, 50, -1, "2.2.2.2", "", ["Running"], "success", "none", "US", "", "", "Linux", "2025-01-01 00:00:00", "2026-03-01 00:00:00", "2026-03-08 00:00:00"),
    ]
    sorted_relays = sort_contact_relays(relays, "ipv4")
    ips = [r["nickname"] for r in sorted_relays]
    assert ips == ["relay_1", "relay_2", "relay_9", "relay_192"]


def test_ipv6_sort_is_numeric_not_lexicographic():
    """IPv6 addresses must sort by numeric value."""
    relays = [
        _relay("FP_B", "relay_b", True, 100, 0, 50, -1, "1.1.1.1", "2001:db8::b", ["Running"], "success", "none", "US", "", "", "Linux", "2025-01-01 00:00:00", "2026-03-01 00:00:00", "2026-03-08 00:00:00"),
        _relay("FP_A", "relay_a", True, 100, 0, 50, -1, "1.1.1.2", "2001:db8::a", ["Running"], "success", "none", "US", "", "", "Linux", "2025-01-01 00:00:00", "2026-03-01 00:00:00", "2026-03-08 00:00:00"),
        _relay("FP_1", "relay_1", True, 100, 0, 50, -1, "1.1.1.3", "2001:db8::1", ["Running"], "success", "none", "US", "", "", "Linux", "2025-01-01 00:00:00", "2026-03-01 00:00:00", "2026-03-08 00:00:00"),
    ]
    sorted_relays = sort_contact_relays(relays, "ipv6")
    names = [r["nickname"] for r in sorted_relays]
    assert names == ["relay_1", "relay_a", "relay_b"]


def test_ip_sort_missing_goes_to_end():
    """Relays with no IP address sort to the end."""
    relay_with_ip = _relay("FP_A", "has_ip", True, 100, 0, 50, -1, "10.0.0.1", "", ["Running"], "success", "none", "US", "", "", "Linux", "2025-01-01 00:00:00", "2026-03-01 00:00:00", "2026-03-08 00:00:00")
    relay_no_ip = _relay("FP_B", "no_ip", True, 100, 0, 50, -1, "10.0.0.2", "", ["Running"], "success", "none", "US", "", "", "Linux", "2025-01-01 00:00:00", "2026-03-01 00:00:00", "2026-03-08 00:00:00")
    relay_no_ip["or_addresses"] = []  # Force no IPv4
    sorted_relays = sort_contact_relays([relay_no_ip, relay_with_ip], "ipv4")
    assert sorted_relays[0]["nickname"] == "has_ip"
    assert sorted_relays[1]["nickname"] == "no_ip"


# =============================================================================
# FLAG-UPTIME CURRENT-FLAGS PARITY (bug fix validation)
# =============================================================================

def test_flag_uptime_sort_uses_current_flags_not_historical():
    """Flag-uptime sort must use only flags the relay currently has.

    A relay with historical Exit uptime data but only current Guard flag
    should sort by Guard uptime, not Exit uptime.
    """
    # Relay has historical Exit data (95%) and Guard data (40%), but only current Guard flag
    relay_guard_only = {
        "fingerprint": "FP_GUARD",
        "nickname": "guard_relay",
        "running": True,
        "observed_bandwidth": 100,
        "flags": ["Guard", "Running"],  # No Exit flag currently
        "_flag_uptime_data": {
            "Exit": {"6_months": {"uptime": 95.0, "data_points": 30}},
            "Guard": {"6_months": {"uptime": 40.0, "data_points": 30}},
        },
        "or_addresses": ["1.1.1.1:9001"],
    }
    # Relay with current Exit flag and 60% uptime
    relay_exit = {
        "fingerprint": "FP_EXIT",
        "nickname": "exit_relay",
        "running": True,
        "observed_bandwidth": 100,
        "flags": ["Exit", "Running"],
        "_flag_uptime_data": {
            "Exit": {"6_months": {"uptime": 60.0, "data_points": 30}},
        },
        "or_addresses": ["2.2.2.2:9001"],
    }

    sorted_relays = sort_contact_relays([relay_guard_only, relay_exit], "flag_uptime")
    # exit_relay (60% Exit) should sort before guard_relay (40% Guard)
    # If bug were present, guard_relay would sort first (95% historical Exit)
    assert sorted_relays[0]["nickname"] == "exit_relay"
    assert sorted_relays[1]["nickname"] == "guard_relay"


def test_flag_uptime_no_current_flags_returns_negative():
    """Relay with no matching current flags gets -1.0 (sorts to end)."""
    from allium.lib.contact_sorting import prioritized_flag_uptime_6m

    relay = {
        "flags": ["Running"],  # No Exit/Guard/Fast
        "_flag_uptime_data": {
            "Exit": {"6_months": {"uptime": 99.0, "data_points": 30}},
        },
    }
    assert prioritized_flag_uptime_6m(relay) == -1.0


# =============================================================================
# SORT-MODE FILE MAP INVARIANTS
# =============================================================================

def test_no_by_bandwidth_html_in_file_map():
    """Bandwidth sort maps to index.html; there must never be a by-bandwidth.html."""
    assert CONTACT_SORT_FILE_MAP["bandwidth"] == "index.html"
    assert "by-bandwidth.html" not in CONTACT_SORT_FILE_MAP.values()


def test_all_sort_modes_have_file_mapping():
    """Every sort mode has a corresponding file."""
    for mode in CONTACT_SORT_MODES:
        assert mode in CONTACT_SORT_FILE_MAP, f"missing file for mode: {mode}"


# =============================================================================
# CONTACT RELAY COUNT (AROI section fallback)
# =============================================================================

def test_contact_relay_count_falls_back_to_section_wrappers():
    """When relay_subset is empty, count relays across AROI sections."""
    base_template_args = {
        "relay_subset": [],
        "contact_validation_status": {
            "validated_relays": [{"relay": _sample_relays()[0]}],
            "misconfigured_relays": [],
            "unauthorized_relays": [{"relay": _sample_relays()[1]}],
            "incomplete_relays": [],
            "not_configured_relays": [{"relay": _sample_relays()[2]}],
        },
    }
    assert contact_relay_count(base_template_args) == 3
