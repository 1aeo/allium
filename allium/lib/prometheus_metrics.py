"""
Prometheus metrics generator for allium.

Generates a static Prometheus exposition format file containing:
  - Section 1: Exit DNS Health (per-relay + aggregates)
  - Section 2: AROI Monitoring (per-relay + aggregates)
  - Meta: build info, generation timestamp, source availability

Schema v1. Metric names and frozen label keys are the public API contract.
See docs/prometheus/README.md for the full schema reference.
"""

import os
import time
from typing import Dict, List, Optional, Set

from .aroi_validation import _check_aroi_fields

# Schema version — bump on breaking changes (metric renames, label key changes)
SCHEMA_VERSION = "1"
GENERATOR = "allium"

# Allowed status values (frozen in schema v1)
_DNS_STATUS_VALUES = ("success", "dns_fail", "timeout", "relay_unreachable")


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------

def _sanitize_prom_label(value) -> str:
    """Escape a value for use inside Prometheus label quotes.

    Prometheus text format requires:
      - backslash  -> \\\\
      - double-quote -> \\"
      - newline -> \\n
    """
    if value is None:
        return ""
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    return s


def _format_labels(labels: Dict[str, str]) -> str:
    """Format a dict of labels into Prometheus label syntax: {k1="v1",k2="v2"}."""
    if not labels:
        return ""
    parts = [f'{k}="{_sanitize_prom_label(v)}"' for k, v in labels.items()]
    return "{" + ",".join(parts) + "}"


def _emit(lines: List[str], name: str, labels: Dict[str, str], value) -> None:
    """Append a single metric line."""
    lines.append(f"{name}{_format_labels(labels)} {value}")


def _emit_help_type(lines: List[str], name: str, help_text: str, type_name: str = "gauge") -> None:
    """Append HELP and TYPE header lines for a metric."""
    lines.append(f"# HELP {name} {help_text}")
    lines.append(f"# TYPE {name} {type_name}")


# ---------------------------------------------------------------------------
# Safe accessors
# ---------------------------------------------------------------------------

def _get_family_id(relay_set, fingerprint: str) -> str:
    """Get the Ed25519 family key for a relay, or empty string.

    Wraps the private ``_fp_to_family_key`` dict with a safe fallback.
    """
    fp_map = getattr(relay_set, "_fp_to_family_key", None)
    if fp_map is None:
        return ""
    return fp_map.get(fingerprint.upper(), "")


def _is_aroi_configured(relay: dict) -> bool:
    """Check whether a relay has all 3 required AROI fields configured.

    Uses the canonical ``_check_aroi_fields`` predicate from aroi_validation.
    """
    contact = relay.get("contact", "") or ""
    fields = _check_aroi_fields(contact)
    return fields.get("complete", False)


def _build_aroi_map(relay_set) -> Dict[str, dict]:
    """Build fingerprint -> {valid, domain, proof_type} from AROI validation data."""
    aroi_data = getattr(relay_set, "aroi_validation_data", None)
    if not aroi_data or "results" not in aroi_data:
        return {}
    result_map: Dict[str, dict] = {}
    for entry in aroi_data.get("results", []):
        fp = entry.get("fingerprint")
        if fp:
            result_map[fp.upper()] = {
                "valid": bool(entry.get("valid")),
                "domain": entry.get("domain") or "",
                "proof_type": entry.get("proof_type") or "",
            }
    return result_map


def _get_verified_aroi(relay: dict, aroi_map: Dict[str, dict],
                       validated_domains: Set[str]) -> str:
    """Determine the verified AROI domain for a relay, or empty string."""
    aroi_domain = relay.get("aroi_domain", "none")
    if aroi_domain and aroi_domain != "none" and aroi_domain in validated_domains:
        return aroi_domain
    return ""


def _parse_timestamp_epoch(ts_str) -> float:
    """Best-effort parse of an ISO timestamp string to epoch seconds. Returns 0 on failure."""
    if not ts_str:
        return 0
    try:
        from datetime import datetime, timezone
        s = str(ts_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.timestamp()
    except Exception:
        # Maybe it's already numeric
        try:
            return float(ts_str)
        except (TypeError, ValueError):
            return 0


# ---------------------------------------------------------------------------
# Meta section (always emitted)
# ---------------------------------------------------------------------------

def _write_meta_section(lines: List[str], relay_set) -> None:
    """Emit build info, generation timestamp, and source-availability metrics."""
    lines.append("# =========================================================================")
    lines.append("# META (always emitted)")
    lines.append("# =========================================================================")
    lines.append("")

    _emit_help_type(lines, "aeo1_build_info",
                    "Metrics schema version and generator metadata")
    _emit(lines, "aeo1_build_info",
          {"schema": SCHEMA_VERSION, "generator": GENERATOR}, 1)
    lines.append("")

    _emit_help_type(lines, "aeo1_generation_timestamp_seconds",
                    "Unix timestamp when this metrics file was generated")
    _emit(lines, "aeo1_generation_timestamp_seconds", {}, int(time.time()))
    lines.append("")

    # Source availability
    dns_data = getattr(relay_set, "exit_dns_health_data", None)
    aroi_data = getattr(relay_set, "aroi_validation_data", None)
    dns_up = 1 if dns_data else 0
    aroi_up = 1 if aroi_data else 0

    _emit_help_type(lines, "aeo1_source_up",
                    "Whether upstream source data was available in this generation (1=yes, 0=no)")
    _emit(lines, "aeo1_source_up", {"source": "exitdnshealth"}, dns_up)
    _emit(lines, "aeo1_source_up", {"source": "aroi"}, aroi_up)
    lines.append("")

    # Last success timestamps (0 if never)
    dns_ts = 0
    if dns_data and isinstance(dns_data, dict):
        meta = dns_data.get("metadata", {})
        dns_ts = _parse_timestamp_epoch(meta.get("timestamp")) or 0

    aroi_ts = 0
    if aroi_data and isinstance(aroi_data, dict):
        meta = aroi_data.get("metadata", {})
        aroi_ts = _parse_timestamp_epoch(meta.get("timestamp")) or 0

    _emit_help_type(lines, "aeo1_source_last_success_timestamp_seconds",
                    "Unix timestamp of the last successful ingest for this source")
    _emit(lines, "aeo1_source_last_success_timestamp_seconds",
          {"source": "exitdnshealth"}, int(dns_ts))
    _emit(lines, "aeo1_source_last_success_timestamp_seconds",
          {"source": "aroi"}, int(aroi_ts))


# ---------------------------------------------------------------------------
# DNS Health section
# ---------------------------------------------------------------------------

def _write_dns_health_section(lines: List[str], relay_set,
                              fp_to_family: callable,
                              aroi_map: Dict[str, dict],
                              validated_domains: Set[str]) -> int:
    """Emit DNS health aggregates and per-relay metrics. Returns exit relay count."""
    dns_data = getattr(relay_set, "exit_dns_health_data", None)
    if not dns_data or not isinstance(dns_data, dict):
        return 0

    metadata = dns_data.get("metadata", {})

    lines.append("")
    lines.append("# =========================================================================")
    lines.append("# SECTION 1: EXIT DNS HEALTH")
    lines.append("# =========================================================================")
    lines.append("")

    # --- Aggregates ---
    _emit_help_type(lines, "aeo1_exit_consensus_relays_count",
                    "Total exit relays in current Tor consensus snapshot")
    _emit(lines, "aeo1_exit_consensus_relays_count", {},
          metadata.get("consensus_relays", 0))
    lines.append("")

    _emit_help_type(lines, "aeo1_exit_tested_relays_count",
                    "Exit relays with DNS test result in latest scan")
    _emit(lines, "aeo1_exit_tested_relays_count", {},
          metadata.get("tested_relays", 0))
    lines.append("")

    _emit_help_type(lines, "aeo1_exit_unreachable_relays_count",
                    "Exit relays unreachable during latest scan")
    _emit(lines, "aeo1_exit_unreachable_relays_count", {},
          metadata.get("unreachable_relays", 0))
    lines.append("")

    # Ratios (0..1)
    tested = metadata.get("tested_relays", 0)
    consensus = metadata.get("consensus_relays", 0)
    dns_success = metadata.get("dns_success", 0)
    success_ratio = round(dns_success / tested, 4) if tested > 0 else 0
    reachability_ratio = round(tested / consensus, 4) if consensus > 0 else 0

    _emit_help_type(lines, "aeo1_exit_dns_success_ratio",
                    "Fraction of tested exit relays with successful DNS result (0..1)")
    _emit(lines, "aeo1_exit_dns_success_ratio", {}, success_ratio)
    lines.append("")

    _emit_help_type(lines, "aeo1_exit_reachability_ratio",
                    "Fraction of consensus exit relays that were reachable in latest scan (0..1)")
    _emit(lines, "aeo1_exit_reachability_ratio", {}, reachability_ratio)
    lines.append("")

    # Error counts by type
    _emit_help_type(lines, "aeo1_exit_dns_errors_count",
                    "DNS error snapshot count by error type in latest scan")
    for error_type in ("fail", "timeout", "wrong_ip", "socks_error", "network_error", "exception"):
        key = f"dns_{error_type}"
        _emit(lines, "aeo1_exit_dns_errors_count",
              {"error_type": error_type}, metadata.get(key, 0))
    lines.append("")

    # Latency stats
    timing = metadata.get("timing", {}).get("total", {})
    _emit_help_type(lines, "aeo1_exit_dns_latency_ms_stat",
                    "Aggregate DNS latency statistics in milliseconds for latest scan")
    for stat_key, prom_val in [("p50_ms", "p50"), ("p95_ms", "p95"), ("p99_ms", "p99"),
                                ("avg_ms", "avg"), ("min_ms", "min"), ("max_ms", "max")]:
        _emit(lines, "aeo1_exit_dns_latency_ms_stat",
              {"stat": prom_val}, timing.get(stat_key, 0))
    lines.append("")

    # Scan timestamp
    _emit_help_type(lines, "aeo1_exit_scan_timestamp_seconds",
                    "Unix timestamp of latest exit DNS health scan")
    scan_ts = _parse_timestamp_epoch(metadata.get("timestamp"))
    _emit(lines, "aeo1_exit_scan_timestamp_seconds", {}, int(scan_ts))
    lines.append("")

    # --- Per-relay metrics ---
    relays = relay_set.json.get("relays", [])
    exit_relays = sorted(
        [r for r in relays if "Exit" in r.get("flags", [])],
        key=lambda r: r.get("fingerprint", "")
    )

    # aeo1_exit_dns_failed
    _emit_help_type(lines, "aeo1_exit_dns_failed",
                    "Whether exit relay DNS health check failed (1=failed, 0=healthy)")
    for relay in exit_relays:
        fp = relay.get("fingerprint", "")
        detail = relay.get("exit_dns_health_detail", "untested")
        failed = 0 if detail == "success" else 1
        # Map detail to allowed status values
        if detail in _DNS_STATUS_VALUES:
            status = detail
        else:
            status = "dns_fail" if failed else "success"
        _emit(lines, "aeo1_exit_dns_failed", {
            "fingerprint": fp,
            "familyid": fp_to_family(fp),
            "status": status,
        }, failed)
    lines.append("")

    # aeo1_exit_dns_latency_ms
    _emit_help_type(lines, "aeo1_exit_dns_latency_ms",
                    "DNS resolution latency in milliseconds for the relay in latest scan")
    for relay in exit_relays:
        latency = relay.get("exit_dns_health_timing_ms")
        if latency is not None:
            fp = relay.get("fingerprint", "")
            _emit(lines, "aeo1_exit_dns_latency_ms", {
                "fingerprint": fp,
                "familyid": fp_to_family(fp),
            }, latency)
    lines.append("")

    # aeo1_exit_dns_consecutive_failures
    _emit_help_type(lines, "aeo1_exit_dns_consecutive_failures",
                    "Consecutive DNS scan failures for this relay")
    for relay in exit_relays:
        fp = relay.get("fingerprint", "")
        cf = relay.get("exit_dns_health_consecutive_failures", 0)
        _emit(lines, "aeo1_exit_dns_consecutive_failures", {
            "fingerprint": fp,
            "familyid": fp_to_family(fp),
        }, cf)
    lines.append("")

    # aeo1_exit_relay_info (non-ABI, mutable labels)
    _emit_help_type(lines, "aeo1_exit_relay_info",
                    "Human-readable exit relay metadata (always 1)")
    for relay in exit_relays:
        fp = relay.get("fingerprint", "")
        _emit(lines, "aeo1_exit_relay_info", {
            "fingerprint": fp,
            "familyid": fp_to_family(fp),
            "nick": relay.get("nickname", ""),
            "verifiedaroi": _get_verified_aroi(relay, aroi_map, validated_domains),
        }, 1)

    return len(exit_relays)


# ---------------------------------------------------------------------------
# AROI section
# ---------------------------------------------------------------------------

def _write_aroi_section(lines: List[str], relay_set,
                        fp_to_family: callable,
                        aroi_map: Dict[str, dict]) -> int:
    """Emit AROI aggregates and per-relay metrics. Returns configured relay count."""
    aroi_data = getattr(relay_set, "aroi_validation_data", None)
    if not aroi_data or not isinstance(aroi_data, dict):
        return 0

    metadata = aroi_data.get("metadata", {})
    statistics = aroi_data.get("statistics", {})

    lines.append("")
    lines.append("# =========================================================================")
    lines.append("# SECTION 2: AROI MONITORING (only AROI-configured relays)")
    lines.append("# =========================================================================")
    lines.append("")

    # --- Aggregates ---
    total_relays = metadata.get("total_relays", 0)
    valid_relays = metadata.get("valid_relays", 0)
    invalid_relays = metadata.get("invalid_relays", 0)

    _emit_help_type(lines, "aeo1_aroi_network_relays_count",
                    "Total relays observed in network snapshot")
    _emit(lines, "aeo1_aroi_network_relays_count", {}, total_relays)
    lines.append("")

    # Count configured relays from the relay data (relays passing _is_aroi_configured)
    all_relays = relay_set.json.get("relays", [])
    configured_relays = [r for r in all_relays if _is_aroi_configured(r)]
    configured_count = len(configured_relays)

    _emit_help_type(lines, "aeo1_aroi_configured_relays_count",
                    "Relays with all required AROI fields configured")
    _emit(lines, "aeo1_aroi_configured_relays_count", {}, configured_count)
    lines.append("")

    _emit_help_type(lines, "aeo1_aroi_valid_relays_count",
                    "AROI-configured relays that validated successfully")
    _emit(lines, "aeo1_aroi_valid_relays_count", {}, valid_relays)
    lines.append("")

    success_ratio = round(valid_relays / configured_count, 4) if configured_count > 0 else 0
    _emit_help_type(lines, "aeo1_aroi_success_ratio",
                    "Fraction of AROI-configured relays that validated (0..1)")
    _emit(lines, "aeo1_aroi_success_ratio", {}, success_ratio)
    lines.append("")

    # Proof type breakdown
    proof_types = statistics.get("proof_types", {})
    _emit_help_type(lines, "aeo1_aroi_proof_type_count",
                    "Snapshot relay counts by proof_type and result")
    for pt_key, prom_pt in [("uri_rsa", "uri-rsa"), ("dns_rsa", "dns-rsa")]:
        pt_data = proof_types.get(pt_key, {})
        _emit(lines, "aeo1_aroi_proof_type_count",
              {"proof_type": prom_pt, "result": "valid"}, pt_data.get("valid", 0))
        _emit(lines, "aeo1_aroi_proof_type_count",
              {"proof_type": prom_pt, "result": "total"}, pt_data.get("total", 0))
    lines.append("")

    # Scan timestamp
    _emit_help_type(lines, "aeo1_aroi_scan_timestamp_seconds",
                    "Unix timestamp of latest AROI validation scan")
    aroi_ts = _parse_timestamp_epoch(metadata.get("timestamp"))
    _emit(lines, "aeo1_aroi_scan_timestamp_seconds", {}, int(aroi_ts))
    lines.append("")

    # --- Per-relay ---
    configured_sorted = sorted(configured_relays, key=lambda r: r.get("fingerprint", ""))

    _emit_help_type(lines, "aeo1_aroi_valid",
                    "Whether relay AROI validation passed (1=valid, 0=failing)")
    for relay in configured_sorted:
        fp = relay.get("fingerprint", "").upper()
        aroi_entry = aroi_map.get(fp, {})
        valid_val = 1 if aroi_entry.get("valid") else 0
        _emit(lines, "aeo1_aroi_valid", {
            "fingerprint": relay.get("fingerprint", ""),
            "familyid": fp_to_family(relay.get("fingerprint", "")),
        }, valid_val)
    lines.append("")

    # aeo1_aroi_relay_info (non-ABI, mutable labels)
    _emit_help_type(lines, "aeo1_aroi_relay_info",
                    "Human-readable AROI relay metadata (always 1)")
    for relay in configured_sorted:
        fp = relay.get("fingerprint", "").upper()
        aroi_entry = aroi_map.get(fp, {})
        _emit(lines, "aeo1_aroi_relay_info", {
            "fingerprint": relay.get("fingerprint", ""),
            "familyid": fp_to_family(relay.get("fingerprint", "")),
            "nick": relay.get("nickname", ""),
            "domain": aroi_entry.get("domain", ""),
            "proof_type": aroi_entry.get("proof_type", ""),
        }, 1)

    return len(configured_sorted)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_prometheus_metrics(relay_set, output_dir: str) -> dict:
    """Generate Prometheus metrics file from enriched relay data.

    Args:
        relay_set: Relays instance with fully processed data.
        output_dir: Directory to write the ``metrics`` file to.

    Returns:
        dict with generation statistics.
    """
    lines: List[str] = []

    # Build shared lookups once
    aroi_map = _build_aroi_map(relay_set)
    validated_domains = getattr(relay_set, "validated_aroi_domains", set()) or set()

    def fp_to_family(fingerprint: str) -> str:
        return _get_family_id(relay_set, fingerprint)

    # Meta — always emitted
    _write_meta_section(lines, relay_set)

    # DNS Health — conditional
    exit_count = _write_dns_health_section(
        lines, relay_set, fp_to_family, aroi_map, validated_domains)
    dns_available = exit_count > 0

    # AROI — conditional
    aroi_count = _write_aroi_section(lines, relay_set, fp_to_family, aroi_map)
    aroi_available = aroi_count > 0

    # Trailing newline + EOF
    lines.append("# EOF")
    lines.append("")

    content = "\n".join(lines)

    # Atomic write: tmp file then rename
    os.makedirs(output_dir, exist_ok=True)
    tmp_path = os.path.join(output_dir, "metrics.tmp")
    final_path = os.path.join(output_dir, "metrics")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.rename(tmp_path, final_path)

    file_size_kb = round(len(content.encode("utf-8")) / 1024, 1)

    return {
        "exit_relays": exit_count,
        "aroi_relays": aroi_count,
        "file_size_kb": file_size_kb,
        "dns_available": dns_available,
        "aroi_available": aroi_available,
    }
