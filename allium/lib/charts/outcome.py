"""Locked C outcome subtitles. Empty on thin history or all-clear."""

from .bands import (
    RATIO_HI,
    RATIO_INVESTIGATE_HI,
    RATIO_INVESTIGATE_LO,
    RATIO_LO,
    RATIO_SCALE_HI,
)
from .identity import peers_word


def format_day(dt):
    """``22 Jul`` without a leading zero. Portable (no ``%-d``)."""
    return "{} {}".format(dt.day, dt.strftime("%b"))


def format_day_span(dates):
    dates = sorted(dates)
    if not dates:
        return ""
    if len(dates) == 1:
        return format_day(dates[0])
    consec = all((dates[i] - dates[i - 1]).days == 1 for i in range(1, len(dates)))
    if consec:
        start, end = dates[0], dates[-1]
        if start.month == end.month and start.year == end.year:
            return "{}–{}".format(start.day, format_day(end))
        return "{}–{}".format(format_day(start), format_day(end))
    return ", ".join(format_day(d) for d in dates)


def _tight_span(span):
    return bool(span) and "," not in span


def _outside_date_bit(outcome, span):
    """`` 22–23 Jul`` or `` all month`` after Outside the band."""
    if _tight_span(span):
        return " {}".format(span)
    if outcome.get("persistent"):
        return " all month"
    if span:
        return " {}".format(span)
    return ""


def _overlay_left_typical(ts, series, bands, day_set):
    """True if the overlay is outside typical on most of those days."""
    if not series or not day_set:
        return None
    tlo, thi = bands["typical_lo"], bands["typical_hi"]
    hits = []
    for t in ts or []:
        if t.date() not in day_set:
            continue
        v = series.get(t)
        if v is None:
            continue
        hits.append(v < tlo or v > thi)
    if not hits:
        return None
    return sum(hits) >= max(1, (len(hits) + 1) // 2)


def summarize_bandwidth_outcome(
    ts, write_m, read_m, advertised_mbit, overlays, bands, overload_status,
    rows=None,
):
    """What the two strips conclude. Used by C subtitles."""
    bands = bands or {}
    overlays = overlays or {}
    tlo = bands.get("typical_lo", RATIO_LO)
    thi = bands.get("typical_hi", RATIO_HI)
    ilo = bands.get("invest_lo", RATIO_INVESTIGATE_LO)
    ihi = bands.get("invest_hi", RATIO_INVESTIGATE_HI)
    role = bands.get("role") or "relay"
    if rows is None:
        rows = [
            (t, w, r, w / r)
            for t, w, r in zip(ts or [], write_m or [], read_m or [])
            if r
        ]
    invest = [row for row in rows if row[3] < ilo or row[3] > ihi]
    if len(rows) < 3:
        return {
            "enough": False,
            "role": role,
            "overloaded": bool(overload_status),
            "invest": invest,
        }
    mean_ratio = sum(row[3] for row in rows) / float(len(rows))
    mean_write = sum(row[1] for row in rows) / float(len(rows))
    mean_read = sum(row[2] for row in rows) / float(len(rows))
    if tlo <= mean_ratio <= thi:
        zone = "typical"
    elif ilo <= mean_ratio <= ihi:
        zone = "uncommon"
    else:
        zone = "investigate"
    off = [row for row in rows if row[3] > RATIO_SCALE_HI]
    write_heavy = [row for row in invest if row[3] > thi]
    read_heavy = [row for row in invest if row[3] < tlo]
    day_set = {row[0].date() for row in invest}
    family_left = _overlay_left_typical(
        ts, overlays.get("operator") or {}, bands, day_set,
    )
    role_left = _overlay_left_typical(
        ts, overlays.get("role") or {}, bands, day_set,
    )
    if not invest:
        who = "with_peers"
    elif role_left:
        who = "role"
    elif family_left:
        who = "family"
    else:
        who = "relay"
    util = (100.0 * mean_write / advertised_mbit) if advertised_mbit else None
    if write_heavy and len(write_heavy) >= len(read_heavy):
        spike = "write"
    elif read_heavy:
        spike = "read"
    else:
        spike = None
    persistent = zone == "investigate" and len(invest) >= max(5, len(rows) // 3)
    if util is None:
        thru = "unknown"
    elif spike and not persistent:
        thru = "spike"
    elif mean_write < 20 and mean_read < 20:
        thru = "crash"
    elif util >= 70:
        thru = "near"
    elif util < 25:
        thru = "low"
    else:
        thru = "steady"
    return {
        "enough": True,
        "role": role,
        "zone": zone,
        "mean_ratio": mean_ratio,
        "mean_write": mean_write,
        "mean_read": mean_read,
        "advertised": advertised_mbit,
        "util": util,
        "invest": invest,
        "off": off,
        "who": who,
        "family_left": family_left,
        "role_left": role_left,
        "spike": spike,
        "persistent": persistent,
        "thru": thru,
        "overloaded": bool(overload_status),
        "restarts": [],
    }


def _util_clause(outcome):
    write = outcome.get("mean_write")
    util = outcome.get("util")
    if write is None:
        return ""
    if util is not None:
        return "{:.0f} Mbit/s ({:.0f}% of advertised)".format(write, util)
    return "{:.0f} Mbit/s".format(write)


def is_all_clear(outcome):
    if not outcome or not outcome.get("enough"):
        return False
    return (
        outcome["thru"] not in ("spike", "crash")
        and not outcome["invest"]
        and outcome["zone"] == "typical"
    )


def format_outcome_subtitle(outcome, which):
    """which: throughput | ratio. Locked C copy only."""
    if not outcome or not outcome.get("enough"):
        return ""
    if is_all_clear(outcome):
        return ""
    role = outcome["role"]
    zone = outcome["zone"]
    n_inv = len(outcome["invest"])
    n_off = len(outcome["off"])
    span = format_day_span([row[0].date() for row in outcome["invest"]])
    util_bit = _util_clause(outcome)

    if which == "throughput":
        if outcome["thru"] == "spike":
            kind = "Write" if outcome["spike"] == "write" else "Read"
            body = "{} spiked".format(kind)
            if span:
                body += " {}".format(span)
            if util_bit:
                body += " · {}".format(util_bit)
            return body
        if outcome["thru"] == "crash":
            body = "Write and read both dropped"
            drop_span = span or "all month"
            body += " {}".format(drop_span)
            if util_bit:
                body += " · {}".format(util_bit)
            return body
        return util_bit

    peers = peers_word(role)
    if outcome["who"] == "role":
        return "Outside the band with other " + peers + _outside_date_bit(
            outcome, span
        )
    if outcome["who"] == "family":
        return (
            "Outside the {} band".format(role)
            + _outside_date_bit(outcome, span)
            + " with the family · other {} stayed".format(peers)
        )
    if outcome["who"] == "relay" and (n_off or n_inv or outcome["persistent"]):
        return (
            "Outside the {} band".format(role)
            + _outside_date_bit(outcome, span)
            + " · family and peers stayed"
        )
    if not outcome["invest"] and zone == "typical":
        return ""
    return (
        "Write/read {:.2f} · inside the {} band with other {}".format(
            outcome["mean_ratio"], role, peers
        )
    )
