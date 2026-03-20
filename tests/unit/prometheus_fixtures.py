"""
Shared fixtures for Prometheus metrics unit tests.
"""


def make_relay(
    fingerprint,
    nickname="TestRelay",
    flags=None,
    contact="",
    dns_status="success",
    dns_timing=1000,
    dns_consecutive=0,
    aroi_domain="none",
):
    return {
        "fingerprint": fingerprint,
        "nickname": nickname,
        "flags": flags or ["Exit", "Fast", "Guard", "Running", "Stable", "Valid"],
        "contact": contact,
        "aroi_domain": aroi_domain,
        "exit_dns_health_status": "success" if dns_status == "success" else "fail",
        "exit_dns_health_detail": dns_status,
        "exit_dns_health_timing_ms": dns_timing,
        "exit_dns_health_consecutive_failures": dns_consecutive,
    }


def make_relay_set(
    relays,
    exit_dns_health_data=None,
    aroi_validation_data=None,
    fp_to_family_key=None,
    validated_aroi_domains=None,
):
    class MockRelaySet:
        pass

    rs = MockRelaySet()
    rs.json = {"relays": relays}
    rs.exit_dns_health_data = exit_dns_health_data
    rs.aroi_validation_data = aroi_validation_data
    rs._fp_to_family_key = fp_to_family_key or {}
    rs.validated_aroi_domains = validated_aroi_domains or set()
    return rs


def sample_dns_metadata():
    return {
        "metadata": {
            "timestamp": "2026-03-08T08:00:00Z",
            "consensus_relays": 100,
            "tested_relays": 95,
            "unreachable_relays": 5,
            "dns_success": 90,
            "dns_fail": 3,
            "dns_timeout": 1,
            "dns_wrong_ip": 1,
            "dns_socks_error": 0,
            "dns_network_error": 0,
            "dns_error": 0,
            "dns_exception": 0,
            "dns_unknown": 0,
            "timing": {
                "total": {
                    "avg_ms": 15000,
                    "min_ms": 200,
                    "max_ms": 30000,
                    "p50_ms": 14000,
                    "p95_ms": 25000,
                    "p99_ms": 28000,
                }
            },
        }
    }


def sample_aroi_data():
    return {
        "metadata": {
            "timestamp": "2026-03-08T10:00:00Z",
            "total_relays": 200,
            "valid_relays": 50,
            "invalid_relays": 150,
        },
        "statistics": {
            "proof_types": {
                "uri_rsa": {"total": 40, "valid": 38},
                "dns_rsa": {"total": 10, "valid": 8},
            }
        },
        "results": [
            {"fingerprint": "AAAA", "valid": True, "domain": "example.com", "proof_type": "uri-rsa"},
            {"fingerprint": "BBBB", "valid": False, "domain": "broken.org", "proof_type": "dns-rsa"},
        ],
    }
