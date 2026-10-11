"""Chart copy: outcome subtitles, frozen role bands and chart identity."""

from datetime import date, timedelta

from allium.lib.charts.bands import (
    CATALOG, band_legend_labels, bands_for_role, census_footnote, ratio_strip_data_hi, role_from_flags,
)
from allium.lib.charts.identity import chart_identity, operator_from_contact
from allium.lib.charts.outcome import format_day_span, ratio_subtitle, ratio_text, throughput_subtitle

from .fixtures import T0

GUARD = bands_for_role("Guard")


def rows(ratios, read=50.0):
    """Daily ``(t, write, read, write/read)`` rows from Sep 1 with a steady read."""
    return [(T0 + timedelta(days=i), read * r, read, r) for i, r in enumerate(ratios)]


def test_format_day_span_joins_runs_and_collapses_long_lists():
    days = [date(2026, 7, d) for d in (22, 23, 25)]
    assert format_day_span(days) == "Jul 22–23, Jul 25"
    assert format_day_span([date(2026, 7, d) for d in (1, 3, 5, 7, 9)], of=30) == "Jul 1–9 (5 of 30 days)"
    assert format_day_span(days, most=0) == "Jul 22–25 (3 days)" and format_day_span(days, of=9, most=-1) == "on 3 of 9 days"
    assert format_day_span([date(2025, 12, 1), date(2025, 12, 11)], timedelta(days=10), year=True) == \
        "Dec 1 '25–Dec 11 '25"


def test_ratio_text_never_prints_a_band_edge_the_value_is_not_on():
    assert ratio_text(1.123, 1.01) == "1.12" and ratio_text(1.01, 1.01) == "1.01"
    assert ratio_text(1.0097, 1.01) == "1.0097" and ratio_text(1.973, 1.97) == "1.973"


def test_throughput_subtitle_states_the_mean_its_share_and_the_peak():
    ts = [T0 + timedelta(days=i) for i in range(4)]
    assert throughput_subtitle(ts, [40, 60, 170, 50], 200.0) == \
        "Write avg 80 Mbit/s (40% of advertised), peak 170 Mbit/s Sep 3"
    # A period's mean over what the relay advertises today is no share of it.
    assert throughput_subtitle(ts, [40, 60, 170, 50], 50.0, "1y") == "Write avg 80 Mbit/s, peak 170 Mbit/s Sep 3 '26"


def test_ratio_subtitle_gives_the_overall_band_and_the_days_beyond_p2_p98_on_each_side():
    assert ratio_subtitle(rows([1.05] * 10), {}, GUARD) == "Write/read 1.05 overall (typical) · inside p2–p98 throughout"
    assert ratio_subtitle([], {}, GUARD) == "Under 50 KB/s throughout: too little traffic to compare"
    # Overall is the ratio of sums, as in the band census: (5 x 1.05 + 3.0 + 3.1 + 0.5) / 8.
    assert ratio_subtitle(rows([1.05] * 5 + [3.0, 3.1, 0.5]), {}, GUARD) == \
        "Write/read 1.48 overall (uncommon) · above p98 Sep 6–7 · below p2 Sep 8"
    scattered = rows([3.0 if i % 2 else 1.05 for i in range(10)])
    assert ratio_subtitle(scattered, {}, GUARD) == "Write/read 2.02 overall (investigate) · above p98 Sep 2–10 (5 of 10 days)"
    assert ratio_subtitle(rows([1.05, 3.0]), {}, GUARD, most=0) == \
        "Write/read 2.02 overall (investigate) · above p98 Sep 2 (1 of 2 days)"


def test_ratio_subtitle_says_whether_family_and_peers_left_the_band_on_the_same_side():
    spike = rows([1.05] * 5 + [3.0, 3.1] + [1.05] * 5)
    base = ratio_subtitle(spike, {}, GUARD)
    assert base == "Write/read 1.38 overall (uncommon) · above p98 Sep 6–7"
    inside = {row[0]: 1.05 for row in spike}
    above, below = ({t: v for t in inside} for v in (3.0, 0.5))
    assert ratio_subtitle(spike, {"role": {}}, GUARD) == base  # not drawn: nothing to say
    assert ratio_subtitle(spike, {"role": inside}, GUARD) == base + " · peers stayed in"
    assert ratio_subtitle(spike, {"role": inside, "family": inside}, GUARD) == base + " · family and peers stayed in"
    assert ratio_subtitle(spike, {"role": inside, "family": above}, GUARD) == base + " · out with the family · peers stayed in"
    assert ratio_subtitle(spike, {"role": above}, GUARD) == base + " · out with other Guards"
    assert ratio_subtitle(spike, {"role": below}, GUARD) == base + " · peers stayed in"  # out, but the other way
    # A median a hair under the typical band is still inside p2–p98.
    assert ratio_subtitle(spike, {"role": {t: 1.009 for t in inside}}, GUARD) == base + " · peers stayed in"


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
