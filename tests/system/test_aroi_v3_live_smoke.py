#!/usr/bin/env python3
"""
Live smoke test for AROI v3 acceptance criterion A.10.

Per PLAN.md (Part A.10):
  > Smoke check: in a debugger, fetch the validation_summary for
  > contact hash 592c6ac73b6520aabeaed46dacbbb914 and confirm
  > is_v3_adopter, pending_onionoo_count, security_incident_count
  > are populated correctly.

This codifies that smoke check as a runnable test against live
upstream data (aroivalidator.1aeo.com + onionoo.torproject.org).

Excluded from the default pytest run (network-dependent); runnable via:
    python3 tests/system/test_aroi_v3_live_smoke.py

Or with pytest, opt-in via the marker:
    pytest -m system tests/system/test_aroi_v3_live_smoke.py
"""
import hashlib
import sys
from unittest.mock import patch

import pytest

# Match the pattern used by tests/system/test_real_api.py: slow + system
# markers so the test is deselected from default `pytest -m "not slow"`
# runs but still discoverable via `pytest -m system tests/system/`.
# Without `slow`, this test would make 2 HTTP requests on every pytest
# invocation — bad for CI flakiness and offline development.
pytestmark = [pytest.mark.slow, pytest.mark.system]


def test_aroi_v3_a10_smoke_against_live_apis():
    """A.10: validate is_v3_adopter / pending_onionoo_count /
    security_incident_count on the user-cited contact hash."""
    pytest.importorskip("requests")
    import requests

    target_hash = "592c6ac73b6520aabeaed46dacbbb914"
    ua = {"User-Agent": "Allium-V3-Smoke-Test/1.0"}

    aroi_data = requests.get(
        "https://aroivalidator.1aeo.com/latest.json",
        headers=ua, timeout=30,
    ).json()
    onionoo_data = requests.get(
        "https://onionoo.torproject.org/details"
        "?fields=fingerprint,nickname,contact,country,first_seen",
        timeout=60,
    ).json()

    from allium.lib.relays import Relays
    from allium.lib.aroi_validation import get_contact_validation_status

    with patch.object(Relays, "__init__", lambda x, **kwargs: None):
        relays_obj = Relays()
        parser = relays_obj._simple_aroi_parsing

    matching = []
    for relay in onionoo_data["relays"]:
        contact = relay.get("contact", "") or ""
        domain, version, proof = parser(contact)
        if domain != "none":
            ghash = hashlib.md5(f"aroi_domain:{domain}".encode()).hexdigest()
            if ghash == target_hash:
                relay.update({
                    "aroi_domain": domain,
                    "aroi_version": version,
                    "aroi_proof_type": proof,
                    "aroi_configured": True,
                })
                matching.append(relay)
        elif hashlib.md5(contact.encode()).hexdigest() == target_hash:
            relay.update({
                "aroi_domain": "none",
                "aroi_version": version,
                "aroi_proof_type": proof,
                "aroi_configured": False,
            })
            matching.append(relay)

    assert matching, f"no relays matched contact hash {target_hash}"

    result = get_contact_validation_status(matching, aroi_data)
    summary = result["validation_summary"]

    # Plan A.10 explicitly asks for these three fields:
    assert "is_v3_adopter" in summary
    assert isinstance(summary["is_v3_adopter"], bool)

    assert "pending_onionoo_count" in summary
    assert isinstance(summary["pending_onionoo_count"], int)
    assert summary["pending_onionoo_count"] >= 0

    assert "security_incident_count" in summary
    assert isinstance(summary["security_incident_count"], int)
    assert summary["security_incident_count"] >= 0

    # A.5 v3 migration metadata present:
    assert summary["v3_tier"] in {
        "none", "explorer", "migrating", "mostly", "complete",
    }
    assert isinstance(summary["is_mixed_migration"], bool)
    assert summary["v2_relay_count"] >= 0
    assert summary["v3_relay_count"] >= 0
    assert 0.0 <= summary["v3_relay_percentage"] <= 100.0


if __name__ == "__main__":
    # Allow direct invocation outside pytest. Need to add the repo
    # root to sys.path so the `allium.lib.*` imports resolve.
    import os, sys as _sys
    _sys.path.insert(
        0,
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    )
    test_aroi_v3_a10_smoke_against_live_apis()
    print("OK: A.10 smoke check passed.")
