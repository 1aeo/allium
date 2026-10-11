"""Chart copy: outcome subtitles, frozen role bands and chart identity."""

from datetime import date, timedelta

from allium.lib.charts.bands import (
    CATALOG, band_legend_labels, bands_for_role, census_footnote, ratio_strip_data_hi, role_from_flags,
)
from allium.lib.charts.identity import chart_identity, operator_from_contact
from allium.lib.charts.outcome import format_day_span, subtitles

from .fixtures import T0

GUARD = bands_for_role("Guard")


def rows(ratios, read=50.0):
    """Daily ``(t, write, read, write/read)`` rows from Sep 1 with a steady read."""
    return [(T0 + timedelta(days=i), read * r, read, r) for i, r in enumerate(ratios)]


def test_format_day_span_joins_runs_and_collapses_long_lists():
    days = [date(2026, 7, d) for d in (22, 23, 25)]
    assert format_day_span(days) == "Jul 22–23, Jul 25"
    assert format_day_span([date(2026, 7, d) for d in (1, 3, 5, 7, 9)]) == "Jul 1–9 (5 days)"
    assert format_day_span([date(2025, 12, 1), date(2025, 12, 11)], timedelta(days=10), year=True) == \
        "Dec 1 '25–Dec 11 '25"


def test_all_clear_has_no_subtitles():
    assert subtitles(rows([1.05] * 10), 100.0, {}, GUARD) == ("", "")
    assert subtitles(rows([1.05, 1.05]), 100.0, {}, GUARD) == ("", "")  # thin history


def test_write_spike_names_its_days():
    spike = rows([1.05] * 5 + [3.0, 3.1] + [1.05] * 5)
    thru, ratio = subtitles(spike, 100.0, {}, GUARD)
    assert thru == "Write spiked Sep 6–7 · 69 Mbit/s (69% of advertised)"
    # Family and peer medians are not drawn here, so the copy claims nothing about them.
    assert ratio == "Outside the Guard band Sep 6–7"
    inside = {row[0]: 1.05 for row in spike}
    assert subtitles(spike, 100.0, {"role": {}}, GUARD)[1] == "Outside the Guard band Sep 6–7"  # nothing to check
    assert subtitles(spike, 100.0, {"role": inside}, GUARD)[1] == "Outside the Guard band Sep 6–7 · peers stayed"
    assert subtitles(spike, 100.0, {"role": inside, "family": inside}, GUARD)[1] == \
        "Outside the Guard band Sep 6–7 · family and peers stayed"
    # The family left the band too: say so, and that the peers stayed only when their line was checked.
    outside = {t: 3.0 for t in inside}
    assert subtitles(spike, 100.0, {"role": inside, "family": outside}, GUARD)[1] == \
        "Outside the Guard band Sep 6–7 with the family · other Guards stayed"
    assert subtitles(spike, 100.0, {"role": {}, "family": outside}, GUARD)[1] == \
        "Outside the Guard band Sep 6–7 with the family"


def test_low_throughput_is_only_a_drop_when_low_against_advertised():
    small = rows([1.05] * 10, read=10.0)
    assert subtitles(small, 10.0, {}, GUARD)[0] == ""  # small but at capacity
    assert subtitles(small, 100.0, {}, GUARD)[0] == \
        "Write and read both dropped all month · 10 Mbit/s (10% of advertised)"
    assert subtitles(small, 100.0, {}, GUARD, period="6m")[0].startswith("Write and read both dropped all 6 months")


def test_peers_outside_the_band_take_the_blame():
    spike = rows([1.05] * 5 + [3.0] + [1.05] * 5)
    role = {row[0]: 2.0 for row in spike}
    assert subtitles(spike, 100.0, {"role": role}, GUARD)[1] == "Outside the band with other Guards Sep 6"


def test_frozen_bands_and_copy():
    assert set(CATALOG["roles"]) == {"Exit+Guard", "Exit", "Guard", "Middle"}  # every role role_from_flags gives
    assert GUARD["role"] == "Guard"
    exit_guard = bands_for_role("Exit+Guard")
    assert ratio_strip_data_hi(exit_guard) > exit_guard["invest_hi"] > 1.70
    assert ratio_strip_data_hi(GUARD) == 1.70
    assert band_legend_labels(GUARD)[0] == "Typical  1.01–1.17  ·  p10–p90"
    assert census_footnote(GUARD) == "4,444 Guards · baseline 15 Aug 2026"


def test_identity_and_roles():
    assert operator_from_contact("Admin url:https://www.1AEO.com/about email:x") == "1aeo.com"
    assert operator_from_contact("url:localhost") == operator_from_contact(None) == ""
    assert chart_identity("jeangrae", "1aeo.com") == "jeangrae  ·  1aeo.com"
    assert chart_identity("1aeo.com", "1AEO.com") == "1aeo.com"
    assert [role_from_flags(f) for f in (["Exit", "Guard"], ["Exit"], ["Guard"], [])] == \
        ["Exit+Guard", "Exit", "Guard", "Middle"]
    assert bands_for_role("Middle")["peers"] == "middle relays"
