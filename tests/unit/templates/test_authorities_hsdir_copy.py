"""The authorities page must describe the HSDir rule Tor actually votes."""

from pathlib import Path


TEMPLATE = Path(__file__).resolve().parents[3] / "allium" / "templates" / "misc-authorities.html"


def test_authorities_page_does_not_apply_wfu_and_25h_to_every_authority():
    """98% WFU and 25-hour time-known are not the HSDir rule for all 9 authorities."""
    text = TEMPLATE.read_text()
    assert "WFU ≥98% (all authorities)" not in text
    assert "most authorities use default" not in text
    assert "MinUptimeHidServDirectoryV2" in text
    assert "96 hours" in text
    assert "moria1" in text
