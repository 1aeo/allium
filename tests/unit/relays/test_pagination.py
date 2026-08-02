"""Pagination regression tests for generated relay tables."""

from allium.lib.page_writer import (
    _paginated_validation_status,
    paginated_filename,
    pagination_context,
)


def test_validation_sections_are_filtered_without_mutating_full_status():
    relay_a = {"fingerprint": "A" * 40}
    relay_b = {"fingerprint": "B" * 40}
    status = {
        "validation_summary": {"total_relays": 2},
        "validated_relays": [
            {"relay": relay_a},
            {"relay": relay_b},
        ],
        "misconfigured_relays": [{"relay": relay_b}],
        "unauthorized_relays": [],
        "incomplete_relays": [],
        "not_configured_relays": [],
        "pending_onionoo_relays": [{"relay": relay_b}],
        "security_incident_relays": [],
    }

    page_status = _paginated_validation_status(status, [relay_a])

    assert page_status["validation_summary"] == {"total_relays": 2}
    assert page_status["validated_relays"] == [{"relay": relay_a}]
    assert page_status["misconfigured_relays"] == []
    assert page_status["pending_onionoo_relays"] == []
    assert len(status["validated_relays"]) == 2


def test_pagination_filenames_and_links_use_clean_routes():
    assert paginated_filename("index.html", 2) == "page-2.html"
    assert paginated_filename("by-status.html", 12) == "by-status-page-12.html"
    assert pagination_context("index.html", 2, 3) == {
        "current": 2,
        "total": 3,
        "previous": "./",
        "next": "page-3",
        "first": "./",
        "last": "page-3",
    }
