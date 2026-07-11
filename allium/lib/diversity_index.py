"""
File: diversity_index.py

Diversity Index for the "Diversity All-Rounders" AROI leaderboard.

The index treats four components as CO-EQUAL (reviewer-approved design,
PR #217 follow-up): Geographic, Platform, Network and Scale. Each component
is a 0-100 sub-score built from a BREADTH half (distinct counts, linear ramp)
and a VOLUME half (relay-ish counts, log ramp), except Scale which is a pure
log ramp of the operator's *diverse relay* count.

    index = mean(geo_score, platform_score, network_score, scale_score)

NETWORK-ADAPTIVE YARDSTICKS (no hardcoded magic caps): every cap is derived
from the live network at each site generation, so "100" always means
"matches today's network leaders/structure" and the bar moves as the network
evolves:

  Breadth caps (structural facts):
    - countries cap  = 10% of countries hosting relays today (floor 5)
    - OS cap         = max distinct OSes run by any single operator today
                       (floor 2) — "as broad as today's most polyglot operator"
    - unique AS cap  = 1% of ASes hosting relays today (floor 10)
  Volume caps (top-5 cohort — the 5th-highest operator value today, floor 2;
  rank-5 rather than max so a single outlier can't stretch the scale):
    - non-EU relays, non-Linux relays, AS rarity sum, diverse relays

DIVERSE RELAYS (Scale component, reviewer "Version A"): a relay counts as
diverse if it differs from the operator's DOMINANT PROFILE — their
most-common OS, most-common country or most-common AS — in at least one
dimension. Intuition: the relays that add spread beyond the operator's main
deployment. A perfect monoculture scores 0 regardless of fleet size.

Percentile-RANK scoring was evaluated and rejected: the operator population
is dominated by single-relay operators, so percentile ranks saturate
(top operators all land at 99-100) and stop discriminating.
"""

import math
from collections import Counter

# Structural cap parameters (fractions of network facts, not magic values)
COUNTRIES_CAP_NETWORK_SHARE = 0.10   # cap = 10% of countries hosting relays
AS_CAP_NETWORK_SHARE = 0.01          # cap = 1% of ASes hosting relays
COUNTRIES_CAP_FLOOR = 5
AS_CAP_FLOOR = 10
OS_CAP_FLOOR = 2
VOLUME_CAP_RANK = 5                  # volume caps anchor to the 5th-highest operator
VOLUME_CAP_FLOOR = 2

# AS rarity tiers that count as "rare" hosting choices (matches
# country_utils.assign_as_rarity_tier vocabulary).
RARE_AS_TIERS = ('rare', 'epic', 'legendary')


def _linear(value, cap):
    """Linear ramp: value/cap, clamped to [0, 1]."""
    if cap <= 0:
        return 0.0
    return min(max(value, 0) / cap, 1.0)


def _log_ramp(value, cap):
    """Log-saturating ramp: log(1+value)/log(1+cap), clamped to [0, 1].

    Rewards early growth strongly and large fleets with diminishing returns,
    so raw size cannot drown the distinct-count halves.
    """
    if cap <= 0:
        return 0.0
    return min(math.log(1 + max(value, 0)) / math.log(1 + cap), 1.0)


def _rank_n_value(values, n=VOLUME_CAP_RANK, floor=VOLUME_CAP_FLOOR) -> float:
    """The n-th highest value in `values` (top-n cohort anchor), floored.

    Falls back to the lowest available value when fewer than n values exist
    (see _volume_yardstick_label for the matching tooltip wording).
    """
    xs = sorted(values, reverse=True)
    if not xs:
        return floor
    return max(xs[min(n - 1, len(xs) - 1)], floor)


def _volume_yardstick_label(n_operators) -> str:
    """Human wording for the volume-cap cohort anchor used in tooltips.

    With fewer than VOLUME_CAP_RANK operators, _rank_n_value() falls back to
    the smallest available value, so describing it as the "5th-largest"
    would be wrong — call it "largest available" instead.
    """
    if n_operators >= VOLUME_CAP_RANK:
        return f"today's {VOLUME_CAP_RANK}th-largest"
    return "today's largest available"


def _mode(counter):
    """Deterministic mode: highest count, ties broken by smallest key.

    Counter.most_common(1) breaks ties by insertion order, which would let
    the same relay multiset produce different dominant profiles (and thus
    different diverse-relay counts) depending on input order.
    """
    return min(counter, key=lambda k: (-counter[k], k))


def count_diverse_relays(operator_relays):
    """Count relays differing from the operator's dominant profile.

    Dominant profile = the operator's most-common platform, most-common
    country and most-common AS (ties broken lexicographically so the result
    is independent of relay input order). A relay is "diverse" if it differs
    in >= 1 of the three (reviewer-approved Version A definition).

    Returns:
        int: number of diverse relays (0 for a perfect monoculture)
    """
    if not operator_relays:
        return 0
    platforms = Counter((r.get('platform') or '?') for r in operator_relays)
    countries = Counter((r.get('country') or '?') for r in operator_relays)
    ases = Counter((r.get('as') or '?') for r in operator_relays)
    mode_platform = _mode(platforms)
    mode_country = _mode(countries)
    mode_as = _mode(ases)
    return sum(
        1 for r in operator_relays
        if (r.get('platform') or '?') != mode_platform
        or (r.get('country') or '?') != mode_country
        or (r.get('as') or '?') != mode_as
    )


def compute_network_caps(aroi_operators, n_countries, n_ases):
    """Derive all index yardsticks from the live network.

    Args:
        aroi_operators (dict): operator_key -> metrics (needs platform_count,
            non_eu_count, non_linux_count, as_rarity_sum, diverse_relay_count)
        n_countries (int): countries hosting relays today
        n_ases (int): ASes hosting relays today

    Returns:
        dict: cap name -> value (all >= their floors)
    """
    ops = aroi_operators.values()
    return {
        'countries': max(math.ceil(COUNTRIES_CAP_NETWORK_SHARE * n_countries), COUNTRIES_CAP_FLOOR),
        'oses': max(max((v['platform_count'] for v in ops), default=0), OS_CAP_FLOOR),
        'unique_as': max(math.ceil(AS_CAP_NETWORK_SHARE * n_ases), AS_CAP_FLOOR),
        'non_eu_relays': _rank_n_value([v['non_eu_count'] for v in ops]),
        'non_linux_relays': _rank_n_value([v['non_linux_count'] for v in ops]),
        'as_rarity_sum': _rank_n_value([v['as_rarity_sum'] for v in ops]),
        'diverse_relays': _rank_n_value([v['diverse_relay_count'] for v in ops]),
    }


def compute_operator_scores(metrics, caps):
    """Compute the four 0-100 sub-scores + composite index for one operator.

    Each dimension score = 100 * (0.5*breadth + 0.5*volume); Scale is a pure
    log ramp of diverse relays. Composite = arithmetic mean of the four.

    Args:
        metrics (dict): operator metrics (country_count, non_eu_count,
            platform_count, non_linux_count, unique_as_count, as_rarity_sum,
            diverse_relay_count)
        caps (dict): from compute_network_caps()

    Returns:
        dict: geo_score, platform_score, network_score, scale_score,
              diversity_index (all int 0-100)
    """
    geo = 100 * (0.5 * _linear(metrics['country_count'], caps['countries'])
                 + 0.5 * _log_ramp(metrics['non_eu_count'], caps['non_eu_relays']))
    # OS breadth ramps from 1 OS (score 0) to the cap; single-OS operators
    # get breadth 0 by construction.
    plat = 100 * (0.5 * _linear(metrics['platform_count'] - 1, max(caps['oses'] - 1, 1))
                  + 0.5 * _log_ramp(metrics['non_linux_count'], caps['non_linux_relays']))
    net = 100 * (0.5 * _linear(metrics['unique_as_count'], caps['unique_as'])
                 + 0.5 * _log_ramp(metrics['as_rarity_sum'], caps['as_rarity_sum']))
    scale = 100 * _log_ramp(metrics['diverse_relay_count'], caps['diverse_relays'])
    scores = {
        'geo_score': round(geo),
        'platform_score': round(plat),
        'network_score': round(net),
        'scale_score': round(scale),
    }
    # Average the ROUNDED components so the displayed Index always equals the
    # mean of the four visible sub-scores (the tooltip states exactly that).
    scores['diversity_index'] = round(
        (scores['geo_score'] + scores['platform_score']
         + scores['network_score'] + scores['scale_score']) / 4
    )
    return scores


def build_cell_tooltips(metrics, caps, n_countries, n_ases, n_operators=VOLUME_CAP_RANK):
    """Build the Option-2 hover tooltips for the four All-Rounders cells.

    Each tooltip states the sub-score, the raw facts, and TODAY'S yardsticks
    (which recompute from the live network every update).

    Args:
        n_operators: size of the operator population — drives the volume
            yardstick wording ("5th-largest" vs "largest available" when
            fewer than VOLUME_CAP_RANK operators exist).

    Returns:
        dict: geo_cell_tooltip, platform_cell_tooltip, network_cell_tooltip,
              scale_cell_tooltip, index_tooltip
    """
    yardstick_note = "Yardsticks recompute from the live network every update."
    cohort = _volume_yardstick_label(n_operators)
    return {
        'geo_cell_tooltip': (
            f"Geographic score {metrics['geo_score']}/100 — {metrics['country_count']} countries "
            f"(yardstick: {caps['countries']} = 10% of the {n_countries} countries hosting relays) "
            f"+ {metrics['non_eu_count']} non-EU relays "
            f"(yardstick: {caps['non_eu_relays']} = {cohort} non-EU fleet). {yardstick_note}"
        ),
        'platform_cell_tooltip': (
            f"Platform score {metrics['platform_score']}/100 — {metrics['platform_count']} distinct OSes incl. Linux "
            f"(yardstick: {caps['oses']} = the most OSes any single operator runs today) "
            f"+ {metrics['non_linux_count']} non-Linux relays "
            f"(yardstick: {caps['non_linux_relays']} = {cohort} non-Linux fleet). {yardstick_note}"
        ),
        'network_cell_tooltip': (
            f"Network score {metrics['network_score']}/100 — {metrics['unique_as_count']} unique ASes, "
            f"{metrics['rare_as_count']} rare (yardstick: {caps['unique_as']} AS = 1% of the {n_ases} ASes hosting relays) "
            f"+ AS rarity sum {metrics['as_rarity_sum']:.0f} "
            f"(yardstick: {caps['as_rarity_sum']:.0f} = {cohort} AS rarity sum). {yardstick_note}"
        ),
        'scale_cell_tooltip': (
            f"Scale score {metrics['scale_score']}/100 — {metrics['diverse_relay_count']} diverse relays: "
            f"relays differing from this operator's most-common OS, country or AS "
            f"(yardstick: {caps['diverse_relays']} = {cohort} diverse fleet). {yardstick_note}"
        ),
        'index_tooltip': (
            f"Diversity Index {metrics['diversity_index']}/100 = average of Geographic "
            f"({metrics['geo_score']}), Platform ({metrics['platform_score']}), Network "
            f"({metrics['network_score']}) and Scale ({metrics['scale_score']}) scores — "
            f"four co-equal components, each measured against yardsticks derived from today's network."
        ),
    }


def annotate_operators(aroi_operators, n_countries, n_ases):
    """Annotate every operator dict with sub-scores, index and cell tooltips.

    Mutates aroi_operators in place (adds geo_score, platform_score,
    network_score, scale_score, diversity_index, *_cell_tooltip,
    index_tooltip) and returns the caps used.
    """
    caps = compute_network_caps(aroi_operators, n_countries, n_ases)
    n_operators = len(aroi_operators)
    for metrics in aroi_operators.values():
        metrics.update(compute_operator_scores(metrics, caps))
        metrics.update(build_cell_tooltips(metrics, caps, n_countries, n_ases, n_operators))
    return caps
