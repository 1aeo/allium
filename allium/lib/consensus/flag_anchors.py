"""
Shared fragment ids for the relay page's Eligibility Flag Vote Details rows.

Two consumers must stay in sync with these ids:
- consensus_evaluation._make_row stamps each table row with `row.anchor`
  (rendered as <tr id="..."> in relay-info.html)
- relay_diagnostics.ISSUE_ANCHORS targets rows from issue diagnostics

Keeping the map in this leaf module (no allium imports, so it can be
loaded from either side without an import cycle) lets both consumers
reference the same values instead of duplicating strings.
"""

# (flag, metric) -> stable fragment id for the row.
FLAG_ROW_ANCHORS = {
    ('Running', 'IPv4 Reachability'): 'flag-running-ipv4',
    ('Running', 'IPv6 Reachability'): 'flag-running-ipv6',
    ('Valid', 'Descriptor'): 'flag-valid',
    ('V2Dir', 'DirPort Available'): 'flag-v2dir',
    ('Fast', 'Speed'): 'flag-fast',
    ('Stable', 'MTBF'): 'flag-stable-mtbf',
    ('Stable', 'Uptime'): 'flag-stable-uptime',
    ('HSDir', 'Prereq: Fast'): 'flag-hsdir-prereq-fast',
    ('HSDir', 'Prereq: Stable'): 'flag-hsdir-prereq-stable',
    ('HSDir', 'Prereq: V2Dir'): 'flag-hsdir-prereq-v2dir',
    ('HSDir', 'WFU'): 'flag-hsdir-wfu',
    ('HSDir', 'Time Known'): 'flag-hsdir-time-known',
    ('Guard', 'Prereq: Fast'): 'flag-guard-prereq-fast',
    ('Guard', 'Prereq: Stable'): 'flag-guard-prereq-stable',
    ('Guard', 'Prereq: V2Dir'): 'flag-guard-prereq-v2dir',
    ('Guard', 'WFU'): 'flag-guard-wfu',
    ('Guard', 'Time Known'): 'flag-guard-time-known',
    ('Guard', 'Bandwidth'): 'flag-guard-bandwidth',
    ('Exit', 'Exit Policy'): 'flag-exit',
    ('MiddleOnly', 'Restriction (by DA)'): 'flag-middleonly',
    ('BadExit', 'Restriction (by DA)'): 'flag-badexit',
}


def flag_row_anchor(flag: str, metric: str) -> str:
    """Stable fragment id for one flag-requirements row.

    Explicit entries win; unmapped rows (future flags/metrics) get a
    deterministic slug so every row still has a deep-linkable id.
    """
    explicit = FLAG_ROW_ANCHORS.get((flag, metric))
    if explicit:
        return explicit
    chars = []
    dash = False
    for ch in f'{flag}-{metric}'.lower():
        if ch.isalnum():
            chars.append(ch)
            dash = False
        elif not dash:
            chars.append('-')
            dash = True
    return 'flag-' + ''.join(chars).strip('-')
