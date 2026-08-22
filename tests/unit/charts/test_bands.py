"""Frozen role-ratio bands and legend copy."""

from allium.lib.charts.bands import (
    band_legend_labels,
    bands_for_flags,
    bands_frozen_from,
    census_footnote,
    format_frozen_baseline,
    load_role_bands,
    ratio_strip_data_hi,
    role_bands_path,
)


def test_shipped_catalog_is_frozen_not_live():
    catalog = load_role_bands()
    assert catalog["frozen_from"] == "2026-08-15 19:00:00"
    assert catalog["period"] == "1_month"
    assert set(catalog["roles"]) == {"Guard", "Exit+Guard", "Exit", "Middle"}
    assert bands_frozen_from(catalog) == "2026-08-15 19:00:00"
    assert role_bands_path().endswith("role_ratio_bands.json")


def test_bands_for_flags_uses_frozen_row():
    guard = bands_for_flags(["Guard", "Fast"])
    assert guard["role"] == "Guard"
    assert guard["typical_lo"] == 1.01
    assert guard["typical_hi"] == 1.17
    assert guard["invest_hi"] == 1.58
    exit_guard = bands_for_flags(["Exit", "Guard"])
    assert exit_guard["role"] == "Exit+Guard"
    assert exit_guard["invest_hi"] == 1.71


def test_ratio_strip_raises_for_exit_guard_p98():
    """Exit+Guard p98 is 1.71 — keep a real top Investigate shelf."""
    assert ratio_strip_data_hi(1.58) == 1.70
    raised = ratio_strip_data_hi(1.71, 0.93)
    assert raised > 1.71
    assert raised >= 1.71 + 0.18 - 1e-9


def test_band_legend_labels_are_range_pct():
    labels = band_legend_labels(bands_for_flags(["Guard"]))
    assert "Typical" in labels["typical"]
    assert "p10–p90" in labels["typical"]
    assert "Uncommon" in labels["uncommon"]
    assert "p2–p10 / p90–p98" in labels["uncommon"]
    assert "Investigate" in labels["investigate"]
    assert "<p2 or >p98" in labels["investigate"]
    assert "Guard" not in labels["typical"]


def test_census_footnote_uses_frozen_date():
    assert format_frozen_baseline("2026-08-15 19:00:00") == "15 Aug 2026"
    text = census_footnote(bands_for_flags(["Guard"]), "2026-08-15 19:00:00")
    assert "Guards" in text
    assert "15 Aug 2026" in text
    assert "4,444" in text
