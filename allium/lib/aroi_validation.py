"""
File: aroi_validation.py

AROI (Authenticated Relay Operator Identifier) Validation Module
Fetches and processes AROI validation data from aroivalidator.1aeo.com
Provides validation metrics for network health dashboard

Uses existing infrastructure from workers.py and file_io_utils.py
Functional approach for simplicity and maintainability

Supports both CIISS ContactInfo specification version 2 (RSA-fingerprint
proofs: dns-rsa, uri-rsa) and version 3 (ed25519 family-ID proofs:
dns-familyid-ed25519, uri-familyid-ed25519). Spec:
https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/
"""

import logging
import re
from collections import defaultdict
from typing import Dict, Optional, List, Tuple
from datetime import datetime

from .string_utils import URL_FIELD_TOKEN_RE

logger = logging.getLogger(__name__)


# =============================================================================
# CIISS spec & validator API constants (single source of truth)
# =============================================================================

# CIISS ContactInfo specification versions Allium recognises.
# v1 is legacy (silently ignored on parse); v2 and v3 are actively supported.
SUPPORTED_CIISSVERSIONS = ("2", "3")

# Proof types per spec version. The aroivalidator latest.json reports
# proof_types with underscored keys (dns-rsa -> dns_rsa); use
# PROOF_TYPE_STAT_KEYS when reading those statistics.
V2_PROOF_TYPES = ("dns-rsa", "uri-rsa")
V3_PROOF_TYPES = ("dns-familyid-ed25519", "uri-familyid-ed25519")
ALL_PROOF_TYPES = V2_PROOF_TYPES + V3_PROOF_TYPES
PROOF_TYPE_STAT_KEYS = tuple(p.replace('-', '_') for p in ALL_PROOF_TYPES)

# Map proof type -> ciissversion that declares it. Used to detect operator
# copy-paste mistakes during migration (e.g. 'ciissversion:2 proof:uri-familyid-ed25519').
#
# Two key forms are populated so callers can look up by either:
#   - dashed form ('dns-rsa')      — used by relay ContactInfo strings
#   - underscored form ('dns_rsa') — used by upstream stats_block keys
# This is the SINGLE source of truth (P3 from reviewer feedback): all
# downstream code (api_diagnostics row formatters, validation cascade,
# template-side classification) must use this dict instead of redefining
# the mapping locally, or proof-type/version labels can drift over time.
PROOF_TYPE_VERSION = {
    **{p: "2" for p in V2_PROOF_TYPES},
    **{p: "3" for p in V3_PROOF_TYPES},
    # Also expose underscored variants — same versions.
    **{p.replace('-', '_'): "2" for p in V2_PROOF_TYPES},
    **{p.replace('-', '_'): "3" for p in V3_PROOF_TYPES},
}


def get_proof_type_version(proof_type):
    """Resolve a proof_type string (in either dashed or underscored form)
    to its CIISS spec version ('2' or '3'). Returns 'unknown' for any
    proof_type not in PROOF_TYPE_VERSION.

    Preferred over inline 'familyid in pt'/'rsa in pt' substring checks
    because it gracefully handles future proof types added to upstream
    (which would silently classify as 'unknown' instead of being
    miscategorized as v2 because they happen to contain 'rsa' or as v3
    because they happen to contain 'family').
    """
    if not proof_type:
        return 'unknown'
    return PROOF_TYPE_VERSION.get(proof_type, 'unknown')

# Schemas of aroivalidator latest.json that this build was tested against.
# When upstream emits a schema number outside this tuple, A.1 logs a
# one-time warning. Schema field appears in metadata.aroivalidator_schema_version.
AROIVALIDATOR_TESTED_SCHEMAS = (1, 2)

# v3 migration tiers (operator-level): inclusive lower bounds.
# Tuned to recognise effort at every stage of migration so an operator
# with 1 v3 relay sees recognition AND a 100%-migrated operator gets a
# distinct top tier.
V3_TIER_EXPLORER = 0.001    # >= 1 v3 relay (almost-zero floor)
V3_TIER_MIGRATING = 0.25    # >= 25% of relays on v3
V3_TIER_MOSTLY = 0.75       # >= 75% of relays on v3
V3_TIER_COMPLETE = 1.0      # 100% of relays on v3
# Threshold used by binary surfaces (listing icons, search-index v3p
# emission). Below this, no marker; at/above it, an operator is "migrating
# enough" to be highlighted. Mirrors V3_TIER_MIGRATING by intent.
V3_LISTING_ICON_THRESHOLD = V3_TIER_MIGRATING


def get_v3_search_index_thresholds() -> Dict[str, int]:
    """Return v3 tier thresholds in search-index JSON units.

    The search index exposes percentages as integers because the Pages
    Function is JavaScript and should not duplicate Allium's float constants.
    ``explorer`` is the one count-based threshold: at least one v3 relay.
    """
    return {
        'explorer': 1,
        'migrating': int(round(V3_TIER_MIGRATING * 100)),
        'mostly': int(round(V3_TIER_MOSTLY * 100)),
        'complete': int(round(V3_TIER_COMPLETE * 100)),
    }


# Module-state for one-time schema warning logging.
_warned_schema_versions = set()


def check_schema_version(validation_data: Optional[Dict],
                         progress_logger=None) -> Optional[int]:
    """Inspect aroivalidator latest.json schema version and warn on unknown.

    Per the upstream contract, ``metadata.aroivalidator_schema_version`` is
    a small integer that bumps when the JSON shape changes in a way
    consumers should notice. We log a single warning per unfamiliar schema
    so we know to update Allium when upstream evolves, but we do NOT
    reject the data — degrade gracefully.

    Args:
        validation_data: Parsed latest.json dict (or None when API down).
        progress_logger: Optional logger callable; falls back to module
            logger.warning when absent so warnings surface in build logs.

    Returns:
        The detected schema version as an int, or None when unavailable.
    """
    if not validation_data or not isinstance(validation_data, dict):
        return None
    metadata = validation_data.get('metadata') or {}
    version = metadata.get('aroivalidator_schema_version')
    if version is None:
        return None
    try:
        version_int = int(version)
    except (ValueError, TypeError):
        return None
    if version_int not in AROIVALIDATOR_TESTED_SCHEMAS and version_int not in _warned_schema_versions:
        _warned_schema_versions.add(version_int)
        msg = (
            f"⚠️  AROI validator schema version {version_int} is newer than "
            f"tested (max: {max(AROIVALIDATOR_TESTED_SCHEMAS)}). Some new "
            f"fields may be ignored. Update Allium to consume them."
        )
        if progress_logger:
            progress_logger(msg)
        else:
            logger.warning(msg)
        _record_warning('schema_mismatch', version_int)
    return version_int


# =============================================================================
# V3_CATEGORY_LABELS: error_category -> human title + pasteable-example hint
# =============================================================================
# Mirrored from the upstream aroivalidator's CATEGORY_INFO dict. Each entry:
#   - 'title': short human description used in tooltips and lists
#   - 'example': a single pasteable line the operator can literally use to fix
#                the issue (NO prose, NO step-by-step instructions)
#   - 'spec_link': optional anchor in the AROI spec for those wanting detail
#
# When upstream adds a new error_category, A.8 emits a one-time warning
# until this dict is updated.
# =============================================================================

def _is_rsa_proof(proof_type):
    """Return True if proof_type identifies a CIISS-v2 (RSA-fingerprint)
    proof family. Helper for picking version-appropriate pasteable
    examples / file paths."""
    if not proof_type:
        return False
    pt = proof_type.lower()
    return pt in ('dns-rsa', 'uri-rsa') or (
        'rsa' in pt and 'familyid' not in pt and 'ed25519' not in pt
    )


def _resolve_example_for_proof(label, proof_type):
    """Pick the version-appropriate example from a V3_CATEGORY_LABELS entry.

    Categories like uri_file_missing / uri_content_mismatch / dns_txt_missing
    can legitimately fire for BOTH v2 (RSA-fingerprint) and v3 (ed25519
    happy-family) relays, but the file paths and TXT-record formats are
    different per spec:

      v2: /.well-known/tor-relay/rsa-fingerprint.txt
          DNS TXT: "we-run-this-tor-relay <fingerprint>"
      v3: /.well-known/tor-relay/ed25519-family-id.txt
          DNS TXT: "we-run-this-tor-ed25519-family-id.<domain>" record

    To avoid showing v3-flavored examples on a v2 relay (the user-reported
    bug: "URI-RSA fingerprint not found" rendered the ed25519 path), each
    label may declare an alternate 'example_v2' field. When the relay's
    proof_type is RSA, we prefer 'example_v2' if present; otherwise we
    fall back to 'example' (the v3 default) so existing v3-only categories
    keep working.
    """
    if not isinstance(label, dict):
        return None
    if _is_rsa_proof(proof_type):
        return label.get('example_v2') or label.get('example')
    return label.get('example')


def _render_pasteable_example(example, fingerprint=None, aroi_domain=None):
    """Substitute placeholders in a V3_CATEGORY_LABELS example so the line is
    literally pasteable for THIS relay/operator.

    Replacements (case-sensitive, single-pass):
      <fingerprint>   -> the relay's actual 40-char Onionoo fingerprint
      <your-domain>   -> the operator's AROI domain (e.g. 'foo.bar')
      foo.bar         -> the operator's AROI domain (used in shape examples)

    The 'foo.bar' substitution is applied last so it doesn't clobber
    earlier '<your-domain>' tokens. Keep the substitution conservative —
    we only touch tokens we know exist in V3_CATEGORY_LABELS examples;
    we do NOT try to mutate prose hints from upstream.
    """
    if not example:
        return example
    rendered = example
    if fingerprint:
        rendered = rendered.replace('<fingerprint>', fingerprint)
    if aroi_domain and aroi_domain != 'none':
        rendered = rendered.replace('<your-domain>', aroi_domain)
        # 'foo.bar' is the placeholder used in shape examples (e.g.
        # 'ContactInfo ... ciissversion:3 url:foo.bar ...'). Only
        # substitute when the example contains that exact token to
        # avoid surprising matches in prose.
        if 'foo.bar' in rendered:
            rendered = rendered.replace('foo.bar', aroi_domain)
    return rendered


V3_CATEGORY_LABELS: Dict[str, Dict[str, Optional[str]]] = {
    'missing_family_ids': {
        'title': 'Onionoo not yet refreshed',
        # Pasteable diagnostic: operator can verify state without waiting blind.
        'example': ('curl "https://onionoo.torproject.org/details?lookup=<fingerprint>'
                    '&fields=family_ids" | jq   # should show your '
                    '.public_family_id within 24h of restarting Tor'),
        'spec_link': None,
    },
    'dns_txt_missing': {
        'title': 'DNS TXT record missing',
        # v3 (ed25519 happy-family) — DNS subdomain pattern.
        'example': ('we-run-this-tor-ed25519-family-id.<your-domain> '
                    'TXT "<contents of .public_family_id>"'),
        # v2 (RSA-fingerprint) — TXT record at the bare domain. Per
        # CIISS v2 the record value is "we-run-this-tor-relay <fp>".
        'example_v2': ('<your-domain> TXT "we-run-this-tor-relay <fingerprint>"   '
                       '# CIISS v2 (RSA-fingerprint proof)'),
        'spec_link': None,
    },
    'dns_content_mismatch': {
        'title': 'DNS TXT does not match family_id',
        'example': ('# TXT must contain .public_family_id contents (43 chars, '
                    'case-sensitive). Never paste .secret_family_key.'),
        'example_v2': ('# v2 TXT record must contain '
                       '"we-run-this-tor-relay <fingerprint>" '
                       'for THIS relay (40-char fingerprint, uppercase hex)'),
        'spec_link': None,
    },
    'uri_file_missing': {
        'title': 'Proof file missing (HTTP 404)',
        # v3 file: ed25519-family-id.txt (43-char family_ids, one/line)
        'example': ('curl https://<your-domain>/.well-known/tor-relay/'
                    'ed25519-family-id.txt   # must return 200'),
        # v2 file: rsa-fingerprint.txt (40-char hex fingerprints, one/line)
        'example_v2': ('curl https://<your-domain>/.well-known/tor-relay/'
                       'rsa-fingerprint.txt   # must return 200'),
        'spec_link': None,
    },
    'uri_content_mismatch': {
        'title': 'Proof file does not contain fingerprint',
        # v3 file: ed25519-family-id.txt (43-char family_id strings)
        'example': ('# /.well-known/tor-relay/ed25519-family-id.txt must list '
                    "this relay's 43-char family_id (one per line)"),
        # v2 file: rsa-fingerprint.txt (40-char RSA fingerprints).
        # User-reported bug: "URI-RSA: Fingerprint not found at <domain>"
        # was rendering the ed25519 path. Now correctly points at
        # rsa-fingerprint.txt with the actual relay's fingerprint
        # substituted in by _render_pasteable_example.
        'example_v2': ('curl https://<your-domain>/.well-known/tor-relay/'
                       'rsa-fingerprint.txt   '
                       "# must contain this relay's 40-char fingerprint "
                       "<fingerprint>"),
        'spec_link': None,
    },
    'wrong_proof_type_rsa': {
        'title': 'v3 contact declares v2 proof type',
        'example': ('ContactInfo ... ciissversion:3 url:foo.bar '
                    'proof:uri-familyid-ed25519'),
        'spec_link': None,
    },
    'missing_proof_field': {
        'title': 'v3 with url: but no proof:',
        'example': ('ContactInfo ... ciissversion:3 url:foo.bar '
                    'proof:dns-familyid-ed25519'),
        'spec_link': None,
    },
    'invalid_url': {
        'title': 'url field is not a parseable domain',
        'example': ('ContactInfo ... url:foo.bar   '
                    '# plain hostname or https://foo.bar'),
        'spec_link': None,
    },
    'unsafe_target': {
        'title': 'url points at private/loopback IP',
        # Pasteable: shows the right shape (public domain) and explicitly
        # forbids IP-literal/loopback/RFC1918 targets.
        'example': ('ContactInfo ... url:your-public-domain.example.com   '
                    '# NOT 127.0.0.1, NOT 10.0.0.1, NOT IP literals'),
        'spec_link': None,
    },
    'redirect_disallowed': {
        'title': 'Proof URI returns HTTP redirect (3xx)',
        # v3: serve ed25519-family-id.txt directly
        'example': ('curl -sI https://<your-domain>/.well-known/tor-relay/'
                    'ed25519-family-id.txt | head -1   '
                    '# must be HTTP/2 200 (no 301/302/308 redirect)'),
        # v2: serve rsa-fingerprint.txt directly
        'example_v2': ('curl -sI https://<your-domain>/.well-known/tor-relay/'
                       'rsa-fingerprint.txt | head -1   '
                       '# must be HTTP/2 200 (no 301/302/308 redirect)'),
        'spec_link': None,
    },
    'secret_key_leaked': {
        'title': '🚨 SECURITY: .secret_family_key published',
        'example': ('tor --keygen-family <newfile>   '
                    '# rotate IMMEDIATELY, then publish new .public_family_id'),
        'spec_link': None,
    },
    'ciissversion_unsupported': {
        'title': 'ciissversion not 2 or 3',
        'example': 'ContactInfo ... ciissversion:3 ...',
        'spec_link': None,
    },
    'transport_error': {
        'title': 'Network/TLS/HTTP error',
        # Pasteable diagnostic: operator can reproduce the failure locally
        # to see if it's an SSL cert, DNS, firewall, or connectivity issue.
        # v3 file path:
        'example': ('curl -v https://<your-domain>/.well-known/tor-relay/'
                    'ed25519-family-id.txt   # check for SSL/timeout/refused'),
        # v2 (URI-RSA) file path: rsa-fingerprint.txt
        'example_v2': ('curl -v https://<your-domain>/.well-known/tor-relay/'
                       'rsa-fingerprint.txt   '
                       '# check for SSL/timeout/refused/HTTP errors'),
        'spec_link': None,
    },
    # Allium-side categories (not from upstream) — used by Part B1 to render
    # the v2/v3 mismatch and v3-informational cases the upstream validator
    # would not see (these are pre-validator parse-time issues).
    'version_proof_mismatch': {
        'title': 'ciissversion and proof type disagree',
        'example': ('# pick consistent pair: ciissversion:3 + '
                    'proof:uri-familyid-ed25519, OR ciissversion:2 + '
                    'proof:uri-rsa'),
        'spec_link': None,
    },
    'v3_informational': {
        'title': 'ciissversion:3 informational (no url)',
        'example': ('# spec-legal: proof is required ONLY when url: is set. '
                    'No action needed unless you want a domain-bound AROI.'),
        'spec_link': None,
    },
}

# Categories that ALWAYS apply to both v2 and v3 (same root cause, same fix
# copy) -- consolidated by A.6's _build_error_rollup. Anything not listed
# here is treated as version-specific.
SHARED_ERROR_CATEGORIES = frozenset({
    'transport_error',
    'redirect_disallowed',
    'unsafe_target',
    'invalid_url',
})

# v3-only error categories (no v2 analog because v2 has no family_ids /
# secret_family_key / ciissversion-aware concepts).
#
# Reviewer-flagged correction: dns_txt_missing / dns_content_mismatch /
# uri_file_missing / uri_content_mismatch were previously listed here but
# they fire for BOTH v2 (RSA-fingerprint proof file/TXT) and v3 (ed25519
# happy-family proof file/TXT). Including them in v3-only caused
# _build_error_rollup() to mis-bucket every v2 proof-file failure as
# v3-only. Removed; those four categories now flow through
# SHARED_ERROR_CATEGORIES handling and are counted correctly in both
# v2 and v3 rollups.
V3_ONLY_ERROR_CATEGORIES = frozenset({
    'missing_family_ids',       # only v3: there are no family_ids in v2
    'wrong_proof_type_rsa',     # only v3: a v3 contact accidentally declares uri-rsa
    'missing_proof_field',      # only v3: v3 has the proof: field; v2 doesn't
    'secret_key_leaked',        # only v3: v2 has no secret_family_key concept
    'ciissversion_unsupported', # only v3: v2 doesn't carry ciissversion at all
})


def classify_v3_tier(v3_relay_count: int, total_relay_count: int) -> str:
    """Classify an operator into a v3 migration tier.

    Returns one of: 'none', 'explorer', 'migrating', 'mostly', 'complete'.

    Single source of truth consumed by every surface (contact pages,
    leaderboards, aggregate listings, search index, Prometheus). When
    tweaking thresholds, change them in V3_TIER_* constants only.
    """
    if total_relay_count <= 0 or v3_relay_count <= 0:
        return 'none'
    pct = v3_relay_count / total_relay_count
    if pct >= V3_TIER_COMPLETE:
        return 'complete'
    if pct >= V3_TIER_MOSTLY:
        return 'mostly'
    if pct >= V3_TIER_MIGRATING:
        return 'migrating'
    # >= 1 v3 relay but < 25%
    return 'explorer'


def _validate_structure(data):
    """Validate data structure has required fields."""
    if not isinstance(data, dict):
        return False
    required_keys = ['metadata', 'statistics', 'results']
    return all(key in data for key in required_keys)


def _calc_percentage(count: int, total: int) -> float:
    """Calculate percentage safely."""
    return (count / total * 100) if total > 0 else 0.0


# Pre-compiled regexes for AROI-field detection. Module-level so v2- and
# v3-aware parsers across the codebase share identical semantics.
_CIISS_VERSION_RE = re.compile(
    r'\bciissversion:(' + '|'.join(SUPPORTED_CIISSVERSIONS) + r')\b',
    re.IGNORECASE,
)
# CIISS legacy: log when a v1 relay is observed (intentional ignore, not a crash).
_CIISS_ANY_VERSION_RE = re.compile(r'\bciissversion:(\d+)\b', re.IGNORECASE)
_PROOF_TYPE_RE = re.compile(
    r'\bproof:(' + '|'.join(re.escape(p) for p in ALL_PROOF_TYPES) + r')\b',
    re.IGNORECASE,
)
_PROOF_ANY_TYPE_RE = re.compile(r'\bproof:([A-Za-z0-9-]+)\b', re.IGNORECASE)
# Shared url: token pattern (string_utils is the single source of truth).
# Keep the _URL_FIELD_RE name: relays.py imports it from this module.
_URL_FIELD_RE = URL_FIELD_TOKEN_RE

# Module-state for one-time warning logs (deduplicates per build).
_warned_unsupported_ciissversion = set()
_warned_unsupported_proof_type = set()

# Module-state for B6: track warnings fired during the current build so the
# API diagnostics page can surface them as a "last warning" feed. Each entry
# is a dict {kind, value, timestamp_iso, count} where:
#   kind:    'unsupported_ciissversion' | 'unsupported_proof_type'
#            | 'unknown_error_category' | 'schema_mismatch'
#   value:   the offending value (e.g. '99', 'foo-proof', 'bar_category', '5')
#   timestamp_iso: ISO timestamp of the FIRST occurrence this build
#   count:   number of times observed this build
# Captured in a list rather than dict-of-sets so the diagnostics
# template can iterate without sorting.
_aroi_warnings_log = []


def _record_warning(kind, value):
    """B6: append to _aroi_warnings_log so api-diagnostics can render
    the per-build warning feed. Idempotent on (kind, value).

    Uses datetime.now(timezone.utc) instead of the deprecated
    datetime.utcnow() (deprecated in Python 3.12+).
    """
    from datetime import datetime as _dt, timezone as _tz
    for entry in _aroi_warnings_log:
        if entry['kind'] == kind and entry['value'] == value:
            entry['count'] += 1
            return
    # ISO format with Z suffix for UTC. timezone-aware now() ensures
    # forward-compatibility with Python 3.12+ where utcnow() is deprecated.
    _now = _dt.now(_tz.utc).replace(tzinfo=None).isoformat(timespec='seconds')
    _aroi_warnings_log.append({
        'kind': kind,
        'value': str(value),
        'timestamp_iso': _now + 'Z',
        'count': 1,
    })


def get_aroi_warnings_log():
    """B6: snapshot of warnings fired during the current build for the
    api-diagnostics template. Returns a list of dicts, sorted by
    timestamp (most recent last)."""
    return list(_aroi_warnings_log)


def reset_aroi_warnings_log():
    """Test-only helper to clear the warning log between assertions."""
    _aroi_warnings_log.clear()
    _warned_unsupported_ciissversion.clear()
    _warned_unsupported_proof_type.clear()
    _warned_unknown_error_categories.clear()
    _warned_schema_versions.clear()


def _check_aroi_fields(contact: str) -> Dict:
    """
    Check which AROI fields are present in a relay's contact string.

    Recognises both CIISS spec v2 (ciissversion:2 + dns-rsa/uri-rsa) and
    CIISS spec v3 (ciissversion:3 + dns-familyid-ed25519 / uri-familyid-ed25519).

    Returns a dict with these keys (all boolean unless noted):
      - has_ciissversion: True if a SUPPORTED ciissversion (2 or 3) is declared
      - has_proof: True if a SUPPORTED proof type is declared
      - has_url: True if a url:... field is present
      - complete: True iff has_ciissversion AND has_proof AND has_url
        (the historical "fully-configured AROI" predicate; preserved for
        Prometheus + downstream consumers)
      - version: '2' or '3' if a supported version is declared; else None
      - proof_type: the lowercased proof type string; else None
      - is_v3_no_proof_compliant: True if ciissversion:3 declared without
        url: (CIISS v3 spec: proof is required only when url is set; an
        operator may declare ciissversion:3 with informational fields
        alone — that's spec-compliant, not "incomplete")
      - version_proof_mismatch: True if a v2-version declares a v3 proof
        type or vice versa (operator copy-paste error during migration)
    """
    if not contact:
        return {
            'has_ciissversion': False,
            'has_proof': False,
            'has_url': False,
            'complete': False,
            'version': None,
            'proof_type': None,
            'is_v3_no_proof_compliant': False,
            'version_proof_mismatch': False,
        }

    # CIISS spec: keys MUST appear only once; if duplicates exist,
    # FIRST wins (matches upstream validator).
    #
    # Reviewer-flagged: previous implementation searched with
    # _CIISS_VERSION_RE first (matches only SUPPORTED versions: 2 or 3)
    # and only fell back to _CIISS_ANY_VERSION_RE when no supported
    # match existed. That hid the case where the FIRST declared token
    # is unsupported (e.g. 'ciissversion:99 ciissversion:2 ...') —
    # the supported-only search would skip the v99 and silently use
    # v2, violating first-wins semantics.
    #
    # New logic: find the FIRST declared ciissversion regardless of
    # support. If the first token is supported, use it. Otherwise log
    # the unsupported value once (for A.8 observability) and leave
    # version=None so the relay gets bucketed as "no AROI" until the
    # operator fixes the contact string.
    # Reviewer-flagged: previously when the FIRST declared token was
    # unsupported (e.g. 'ciissversion:99'), version was set to None and
    # downstream _categorize_by_missing_fields() bucketed the relay as
    # "missing field". That hid the operator-actionable distinction
    # between "didn't declare any version" and "declared an unsupported
    # version". Fix: keep the raw first token in `version` even when
    # unsupported, while STILL calling _record_warning so the
    # build-time observability log captures the unknown value. The
    # existing has_ciissversion / complete computation below uses
    # bool(version), so the relay now appears as "version present"
    # in the aroi_fields dict — the explicit-but-unsupported case
    # gets routed accordingly by the caller (typically lands in the
    # version_proof_mismatch bucket because PROOF_TYPE_VERSION can't
    # match the unsupported value).
    version = None
    any_match = _CIISS_ANY_VERSION_RE.search(contact)
    if any_match:
        first_v = any_match.group(1)
        if first_v in SUPPORTED_CIISSVERSIONS:
            version = first_v
        else:
            # Preserve the raw unsupported token (don't discard it).
            version = first_v
            if first_v not in _warned_unsupported_ciissversion:
                _warned_unsupported_ciissversion.add(first_v)
                logger.info(
                    "AROI: encountered unsupported ciissversion:%s — ignoring "
                    "(supported: %s)", first_v, ','.join(SUPPORTED_CIISSVERSIONS)
                )
                _record_warning('unsupported_ciissversion', first_v)

    # Same first-wins logic for proof_type — same preservation
    # treatment for unsupported proof types.
    proof_type = None
    any_match = _PROOF_ANY_TYPE_RE.search(contact)
    if any_match:
        first_pt = any_match.group(1).lower()
        if first_pt in ALL_PROOF_TYPES:
            proof_type = first_pt
        else:
            # Preserve the raw unsupported proof type (don't discard).
            proof_type = first_pt
            if first_pt not in _warned_unsupported_proof_type:
                _warned_unsupported_proof_type.add(first_pt)
                logger.warning(
                    "AROI: unknown proof type '%s' — update ALL_PROOF_TYPES "
                    "in aroi_validation.py to recognise new proof types", first_pt
                )
                _record_warning('unsupported_proof_type', first_pt)

    has_url = bool(_URL_FIELD_RE.search(contact))

    # Detect version/proof mismatch (e.g. ciissversion:2 with
    # proof:uri-familyid-ed25519). This is a real-world copy-paste error
    # during migration and we want to surface it as "incomplete /
    # version-proof mismatch" rather than silently accepting it.
    version_proof_mismatch = False
    if version and proof_type:
        expected_version = PROOF_TYPE_VERSION.get(proof_type)
        if expected_version and expected_version != version:
            version_proof_mismatch = True

    has_ciissversion = bool(version)
    has_proof = bool(proof_type)
    # 'complete' AROI semantics: all 3 fields present, version+proof
    # match (mismatched pairs DO NOT count as complete).
    complete = (has_ciissversion and has_proof and has_url
                and not version_proof_mismatch)
    is_v3_no_proof_compliant = (version == '3' and not has_url)

    return {
        'has_ciissversion': has_ciissversion,
        'has_proof': has_proof,
        'has_url': has_url,
        'complete': complete,
        'version': version,
        'proof_type': proof_type,
        'is_v3_no_proof_compliant': is_v3_no_proof_compliant,
        'version_proof_mismatch': version_proof_mismatch,
    }


def _categorize_by_missing_fields(aroi_fields: Dict, has_contact: bool) -> str:
    """
    Categorize a relay's AROI configuration based on which fields are
    missing or inconsistent.

    Args:
        aroi_fields: Dict from _check_aroi_fields() with at least
            has_ciissversion, has_proof, has_url, version_proof_mismatch,
            is_v3_no_proof_compliant.
        has_contact: True if relay has a non-empty contact field.

    Returns one of:
      - 'no_contact':            relay has no contact field
      - 'no_aroi_info':          contact present, 0 AROI fields
      - 'missing_two_aroi':      contact + 1 AROI field; missing 2
      - 'no_proof':              has ciissversion + url; missing proof
      - 'no_domain':             has ciissversion + proof; missing url
      - 'no_ciissversion':       has proof + url; missing ciissversion
      - 'version_proof_mismatch': has all 3 BUT proof type doesn't match
                                  declared ciissversion (e.g. v2 +
                                  uri-familyid-ed25519). Operator
                                  copy-paste error during migration.
      - 'v3_informational':      ciissversion:3 declared without url:.
                                  Spec-legal (proof not required when
                                  url is absent); not an issue.
      - 'no_aroi':               defensive fallback (shouldn't reach)
    """
    # Check version/proof mismatch BEFORE missing-fields check; a relay
    # with all 3 fields-present but mismatched proof is qualitatively
    # different from "no AROI" and gets its own actionable category.
    if aroi_fields.get('version_proof_mismatch'):
        return 'version_proof_mismatch'

    # CIISS v3 spec-compliant url-less informational case: ciissversion:3
    # may appear with informational fields (email, donations, etc.) and
    # no url. proof is required only when url is set, so absence of
    # both is spec-legal — not "incomplete".
    if aroi_fields.get('is_v3_no_proof_compliant'):
        return 'v3_informational'

    fields_present = sum([
        aroi_fields['has_ciissversion'],
        aroi_fields['has_proof'],
        aroi_fields['has_url'],
    ])

    if not has_contact:
        return 'no_contact'  # Empty/missing contact field

    if fields_present == 0:
        return 'no_aroi_info'  # Has contact but no AROI fields at all
    if fields_present == 1:
        return 'missing_two_aroi'  # Has 1 AROI field, missing 2

    # Has exactly 2 fields (missing exactly 1) - be specific
    if not aroi_fields['has_proof']:
        return 'no_proof'
    if not aroi_fields['has_url']:
        return 'no_domain'
    if not aroi_fields['has_ciissversion']:
        return 'no_ciissversion'

    # Shouldn't reach here if upstream callers already handled
    # `complete=True` — defensive fallback.
    return 'no_aroi'


def _deduplicate_fingerprint_not_found_error(error: str) -> str:
    """
    Deduplicate error messages that repeat "Fingerprint not found in URL" for multiple URLs.
    
    Example input:
        "Fingerprint not found in https://prsv.ch/.../rsa-fingerprint.txt; Fingerprint not found in https://www.prsv.ch/.../rsa-fingerprint.txt"
    
    Example output:
        "Fingerprint not found in https://prsv.ch/.../rsa-fingerprint.txt, https://www.prsv.ch/.../rsa-fingerprint.txt"
    """
    # Pattern to match "Fingerprint not found in URL" segments separated by semicolons
    pattern = r'Fingerprint not found in ([^;]+)'
    matches = re.findall(pattern, error)
    
    if len(matches) > 1:
        # Multiple "Fingerprint not found" messages - combine the URLs
        urls = [url.strip() for url in matches]
        return "Fingerprint not found in " + ", ".join(urls)
    
    # No deduplication needed
    return error


def _simplify_error_message(error: str) -> tuple:
    """
    Simplify a verbose error message into a short description with protocol prefix.
    
    Returns:
        Tuple of (simplified_message, proof_type) where proof_type is 'dns', 'uri', or 'other'
    """
    e = error.lower()
    
    # DNS-specific errors (check first as they're more specific)
    if 'nxdomain' in e or 'no such domain' in e:
        return ("DNS: Domain not found (NXDOMAIN)", 'dns')
    if 'servfail' in e:
        return ("DNS: Server failure (SERVFAIL)", 'dns')
    if 'txt record' in e or ('txt' in e and 'dns' in e):
        return ("DNS: TXT record not found", 'dns') if 'not found' in e or 'missing' in e else ("DNS: TXT record error", 'dns')
    if 'dns' in e and 'lookup' in e:
        return ("DNS: Lookup failed", 'dns')
    
    # SSL/TLS errors - check for SSLV3_ALERT_HANDSHAKE_FAILURE specifically
    if 'sslv3_alert_handshake_failure' in e or ('ssl' in e and 'handshake' in e and 'alert' in e):
        return ("URI: SSL/TLS v3 handshake failed", 'uri')
    if 'ssl' in e and ('handshake' in e or 'alert' in e):
        return ("URI: SSL/TLS handshake failed", 'uri')
    if 'certificate' in e:
        return ("URI: SSL certificate error", 'uri')
    
    # HTTP errors (check after DNS patterns)
    if '404' in error or ('not found' in e and 'dns' not in e and 'txt' not in e):
        return ("URI: Fingerprint file not found (404)", 'uri') if 'fingerprint' in e else ("URI: Proof file not found (404)", 'uri')
    if '403' in error or 'forbidden' in e:
        return ("URI: Access forbidden (403)", 'uri')
    if 'connection refused' in e or 'refused' in e:
        return ("URI: Connection refused", 'uri')
    if 'timeout' in e:
        return ("URI: Connection timeout", 'uri')
    if 'max retries exceeded' in e:
        return ("URI: Server unreachable", 'uri')
    if 'name or service not known' in e or 'nameresolutionerror' in e:
        return ("URI: Domain resolution failed", 'uri')
    
    # Fingerprint errors
    if 'fingerprint' in e:
        if 'mismatch' in e or 'does not match' in e:
            return ("DNS: Fingerprint mismatch", 'dns') if 'http' not in e and 'uri' not in e else ("URI: Fingerprint mismatch", 'uri')
        if 'not found' in e:
            return ("URI: Fingerprint not in proof", 'uri')
    
    # Generic HTTP errors
    if 'failed to fetch' in e or ('http' in e and 'dns' not in e) or 'https' in e:
        return ("URI: Connection error", 'uri')
    
    # Unknown - truncate if too long
    return (error[:47] + "...", 'other') if len(error) > 50 else (error, 'other')


def _simplify_and_categorize_errors(errors: Dict[str, int]) -> Dict[str, Dict[str, int]]:
    """
    Simplify error messages and categorize them by proof type.
    
    Args:
        errors: Dict mapping raw error message -> count
        
    Returns:
        Dict with keys 'all', 'dns', 'uri' mapping simplified error -> count
    """
    result = {'all': {}, 'dns': {}, 'uri': {}}
    
    for raw_error, count in errors.items():
        simplified, proof_type = _simplify_error_message(raw_error)
        
        # Add to 'all' category
        result['all'][simplified] = result['all'].get(simplified, 0) + count
        
        # Add to specific proof type category
        if proof_type in ('dns', 'uri'):
            result[proof_type][simplified] = result[proof_type].get(simplified, 0) + count
    
    return result


def _categorize_relay_by_validation(relay: Dict, validation_map: Dict) -> str:
    """
    Categorize a relay by its AROI validation status (v2 + v3 aware).

    A relay needs all 3 required fields with a CONSISTENT (version, proof)
    pair to count as "complete AROI":
      - CIISS v2: ciissversion:2 + proof:(dns-rsa|uri-rsa) + url:<domain>
      - CIISS v3: ciissversion:3 + proof:(dns-familyid-ed25519
                                          |uri-familyid-ed25519) + url:<domain>

    Args:
        relay: Relay dictionary from Onionoo API
        validation_map: Map of fingerprint -> upstream validation result

    Returns one of:
        - 'validated':              has complete AROI + upstream said valid
        - 'unvalidated':            has complete AROI + upstream said invalid
        - 'no_proof', 'no_domain', 'no_ciissversion':
                                    has 2-of-3 fields, missing the named one
        - 'missing_two_aroi':       has 1 field, missing 2
        - 'no_aroi_info':           has contact but 0 AROI fields
        - 'no_contact':             no contact field at all
        - 'version_proof_mismatch': 3 fields present but proof type
                                    disagrees with declared ciissversion
                                    (e.g. ciissversion:2 + proof:uri-familyid-ed25519)
        - 'v3_informational':       ciissversion:3 with no url: (spec-legal,
                                    not "incomplete")
    """
    fingerprint = relay.get('fingerprint')
    aroi_domain = relay.get('aroi_domain', 'none')
    contact = relay.get('contact', '')
    
    # Check if has complete AROI setup (all 3 fields)
    has_complete_aroi = aroi_domain and aroi_domain != 'none'
    
    if fingerprint in validation_map:
        result = validation_map[fingerprint]
        if result.get('valid', False):
            return 'validated'
        
        error = result.get('error', '')
        
        # If validation attempted but relay has complete AROI, it's a real validation failure
        if has_complete_aroi:
            return 'unvalidated'
        
        # Check which specific fields are missing
        if error in ('No contact information', 'Missing AROI fields'):
            aroi_fields = _check_aroi_fields(contact)
            if not aroi_fields['complete']:
                has_contact = bool(contact and contact.strip())
                return _categorize_by_missing_fields(aroi_fields, has_contact)
            return 'no_aroi'
        else:
            # Real validation error (not missing fields)
            return 'unvalidated'
    else:
        # Not in validation map - use local analysis
        if has_complete_aroi:
            return 'unvalidated'
        
        # Check which fields are present - use helper to avoid duplication
        aroi_fields = _check_aroi_fields(contact)
        has_contact = bool(contact and contact.strip())
        return _categorize_by_missing_fields(aroi_fields, has_contact)


# Module-state for one-time error-category warnings.
_warned_unknown_error_categories = set()


def _warn_unknown_error_categories(category_counts: Dict[str, int]) -> None:
    """A.8 helper: log once per unknown error_category seen in upstream data.

    When upstream aroivalidator adds a new failure category we don't yet
    have a V3_CATEGORY_LABELS entry for, surface it as a build-time
    warning so we know to update the labels dict.
    """
    for category, count in (category_counts or {}).items():
        if count <= 0:
            continue
        if category in V3_CATEGORY_LABELS:
            continue
        if category in _warned_unknown_error_categories:
            continue
        _warned_unknown_error_categories.add(category)
        logger.warning(
            "AROI: unknown error_category '%s' (count=%d) — update "
            "V3_CATEGORY_LABELS in aroi_validation.py", category, count
        )
        _record_warning('unknown_error_category', category)


def _build_error_rollup(
    relay_results: List[Dict],
) -> Tuple[List[Tuple[str, str, int]], List[Tuple[str, str, int]], List[Tuple[str, str, int]]]:
    """A.6: Consolidate v2 and v3 error counts into shared / v2_only / v3_only.

    Args:
        relay_results: List of per-relay validation result dicts (each dict
            ideally has 'valid', 'ciissversion', 'error_category', 'error').

    Returns:
        Three lists of (category, title, count) tuples sorted by count desc:
          - shared: error categories that apply to BOTH v2 and v3 with the
                    same root cause and same fix copy (consolidated).
          - v2_only: errors observed only on v2 relays.
          - v3_only: errors observed only on v3 relays.

    Categories without an entry in V3_CATEGORY_LABELS get a synthetic
    title from the raw category string. Relays with no error_category
    (older cached upstream responses, before schema v2) are ignored —
    the legacy substring rollup in `_simplify_and_categorize_errors`
    still handles those.
    """
    shared_counts: Dict[str, int] = defaultdict(int)
    v2_counts: Dict[str, int] = defaultdict(int)
    v3_counts: Dict[str, int] = defaultdict(int)

    for r in relay_results or ():
        if r.get('valid'):
            continue
        category = r.get('error_category')
        if not category:
            continue  # Pre-schema-v2 cached entry, fall through to legacy path.
        version = r.get('ciissversion') or ''
        if category in SHARED_ERROR_CATEGORIES:
            shared_counts[category] += 1
        elif version == '3' or category in V3_ONLY_ERROR_CATEGORIES:
            v3_counts[category] += 1
        elif version == '2':
            v2_counts[category] += 1
        else:
            # No version info: bucket as v2_only (today's heuristic).
            v2_counts[category] += 1

    def _format(counts: Dict[str, int]) -> List[Tuple[str, str, int]]:
        rows = []
        for cat, cnt in counts.items():
            label = V3_CATEGORY_LABELS.get(cat) or {}
            title = label.get('title') or cat.replace('_', ' ').title()
            rows.append((cat, title, cnt))
        rows.sort(key=lambda x: x[2], reverse=True)
        return rows

    return _format(shared_counts), _format(v2_counts), _format(v3_counts)


def _log_aroi_build_summary(metrics: Dict, progress_logger=None) -> None:
    """A.8: Emit a one-line summary of v2 + v3 stats during the build.

    Helps catch regressions and silently dropped relays at a glance.
    """
    msg = (
        f"\u2713 AROI: schema v{metrics.get('aroi_schema_version', '?')}, "
        f"{metrics.get('v2_valid', 0)}/{metrics.get('v2_total', 0)} v2 valid, "
        f"{metrics.get('v3_valid', 0)}/{metrics.get('v3_total', 0)} v3 valid"
    )
    declared = metrics.get('ciissversion_declared') or {}
    if declared:
        parts = [
            f"v{k}:{declared[k]}" if k != 'none' else f"none:{declared[k]}"
            for k in sorted(declared)
        ]
        msg += f" \u2014 declared {', '.join(parts)}"
    if progress_logger:
        progress_logger(msg)
    else:
        logger.info(msg)


def calculate_aroi_validation_metrics(relays: List[Dict], validation_data: Optional[Dict] = None, 
                                       calculate_operator_metrics: bool = True) -> Dict:
    """
    Calculate AROI validation metrics for network health dashboard.
    
    Analyzes relay fingerprints against validation data to determine:
    - RELAY-level: How many relays have valid AROI proofs (dns-rsa or uri-rsa)
    - OPERATOR-level: How many operators (domains) are validated/invalid (if enabled)
    - Success rates by proof type (dns-rsa vs uri-rsa)
    - Failure breakdown by proof type
    
    Args:
        relays: List of relay dictionaries from Onionoo API
        validation_data: Optional validation data from aroivalidator.1aeo.com
        calculate_operator_metrics: If True, also calculate operator-level metrics in same pass
        
    Returns:
        Dict containing validation metrics for health dashboard (relay + operator level)
    """
    # Initialize metrics with safe defaults. Per-proof-type and per-version
    # keys are seeded in a single loop so adding a future proof type is one
    # PROOF_TYPE_STAT_KEYS line, not 3 lines per type.
    metrics = {
        'aroi_validated_count': 0,
        'aroi_unvalidated_count': 0,
        'aroi_no_proof_count': 0,
        'aroi_no_domain_count': 0,
        'aroi_no_ciissversion_count': 0,
        'relays_no_contact': 0,
        'relays_no_aroi_info': 0,
        'relays_missing_two_aroi': 0,
        'relays_version_proof_mismatch': 0,
        'relays_v3_informational': 0,
        'aroi_validated_percentage': 0.0,
        'aroi_unvalidated_percentage': 0.0,
        'aroi_no_proof_percentage': 0.0,
        'aroi_no_domain_percentage': 0.0,
        'aroi_no_ciissversion_percentage': 0.0,
        'relays_no_contact_percentage': 0.0,
        'relays_no_aroi_info_percentage': 0.0,
        'relays_missing_two_aroi_percentage': 0.0,
        'relays_version_proof_mismatch_percentage': 0.0,
        'relays_v3_informational_percentage': 0.0,
        'aroi_validation_success_rate': 0.0,
        'validation_data_available': False,
        'validation_timestamp': 'Unknown',
        'top_3_aroi_countries': [],
        'relay_error_top5': [],
        'operator_error_top5': [],
        'dns_error_top5': [],
        'uri_error_top5': [],
        'no_aroi_reasons_top5': [],
        # ciissversion adoption (sourced directly from upstream when present)
        'ciissversion_declared': {},
        'ciissversion_validated': {},
        # v3 failure-category counts (from upstream's v3_failure_categories
        # statistic; aggregated across all v3 relays in a single batch)
        'v3_failure_categories': {},
        # Aggregate v2 + v3 totals (computed below from per-proof-type counts)
        'v2_total': 0, 'v2_valid': 0, 'v2_success_rate': 0.0,
        'v3_total': 0, 'v3_valid': 0, 'v3_success_rate': 0.0,
        # v2/v3 consolidated error rollup (from _build_error_rollup)
        'error_rollup_shared': [],
        'error_rollup_v2_only': [],
        'error_rollup_v3_only': [],
    }
    # Seed per-proof-type *_total / *_valid / *_success_rate keys for ALL
    # known proof types (4 today: dns_rsa, uri_rsa, dns_familyid_ed25519,
    # uri_familyid_ed25519). Pre-seeded so templates can iterate without
    # defensive .get() everywhere.
    for stat_key in PROOF_TYPE_STAT_KEYS:
        metrics[f'{stat_key}_total'] = 0
        metrics[f'{stat_key}_valid'] = 0
        metrics[f'{stat_key}_success_rate'] = 0.0
    
    if not relays:
        return metrics
    
    total_relays = len(relays)
    
    # If no validation data available, return early with basic counts
    if not validation_data or 'results' not in validation_data:
        # Count relays with/without AROI based on contact info
        unique_aroi_domains = set()  # Track for operator metrics
        
        for relay in relays:
            aroi_domain = relay.get('aroi_domain', 'none')
            contact = relay.get('contact', '')
            
            if aroi_domain and aroi_domain != 'none':
                # Has AROI domain (all 3 fields) but no validation data available
                metrics['aroi_unvalidated_count'] += 1
                if calculate_operator_metrics:
                    unique_aroi_domains.add(aroi_domain)
            else:
                # Missing some or all AROI fields - categorize specifically using helper
                aroi_fields = _check_aroi_fields(contact)
                has_contact = bool(contact and contact.strip())
                category = _categorize_by_missing_fields(aroi_fields, has_contact)
                if category == 'no_proof':
                    metrics['aroi_no_proof_count'] += 1
                elif category == 'no_domain':
                    metrics['aroi_no_domain_count'] += 1
                elif category == 'no_ciissversion':
                    metrics['aroi_no_ciissversion_count'] += 1
                elif category == 'no_contact':
                    metrics['relays_no_contact'] += 1
                elif category == 'no_aroi_info':
                    metrics['relays_no_aroi_info'] += 1
                elif category == 'missing_two_aroi':
                    metrics['relays_missing_two_aroi'] += 1
                elif category == 'version_proof_mismatch':
                    metrics['relays_version_proof_mismatch'] += 1
                elif category == 'v3_informational':
                    metrics['relays_v3_informational'] += 1
        
        # Calculate percentages using helper function
        metrics['aroi_unvalidated_percentage'] = _calc_percentage(metrics['aroi_unvalidated_count'], total_relays)
        metrics['aroi_no_proof_percentage'] = _calc_percentage(metrics['aroi_no_proof_count'], total_relays)
        metrics['aroi_no_domain_percentage'] = _calc_percentage(metrics['aroi_no_domain_count'], total_relays)
        metrics['aroi_no_ciissversion_percentage'] = _calc_percentage(metrics['aroi_no_ciissversion_count'], total_relays)
        metrics['relays_no_contact_percentage'] = _calc_percentage(metrics['relays_no_contact'], total_relays)
        metrics['relays_no_aroi_info_percentage'] = _calc_percentage(metrics['relays_no_aroi_info'], total_relays)
        metrics['relays_missing_two_aroi_percentage'] = _calc_percentage(metrics['relays_missing_two_aroi'], total_relays)
        # Reviewer-flagged: previously these two newly-added counters
        # were incremented in the early-return fallback branch but
        # their *_percentage companions were never computed. Compute
        # them here alongside the rest so downstream code (templates,
        # network-health dashboard, prometheus) can rely on the
        # _percentage field always being present.
        metrics['relays_version_proof_mismatch_percentage'] = _calc_percentage(
            metrics['relays_version_proof_mismatch'], total_relays
        )
        metrics['relays_v3_informational_percentage'] = _calc_percentage(
            metrics['relays_v3_informational'], total_relays
        )
        
        # Add operator-level metrics even without validation data
        if calculate_operator_metrics:
            metrics['unique_aroi_domains_count'] = len(unique_aroi_domains)
            metrics['validated_aroi_domains_count'] = 0  # Can't validate without data
            metrics['invalid_aroi_domains_count'] = len(unique_aroi_domains)  # All unknown
            metrics['validated_aroi_domains_percentage'] = 0.0
            metrics['invalid_aroi_domains_percentage'] = 100.0 if len(unique_aroi_domains) > 0 else 0.0
            metrics['top_operators_text'] = "Validation data not available"
            metrics['_validated_domain_set'] = set()  # Empty set for IPv6 calculation
        
        return metrics
    
    # Extract validation metadata
    metadata = validation_data.get('metadata', {})
    statistics = validation_data.get('statistics', {})
    
    metrics['validation_data_available'] = True
    metrics['validation_timestamp'] = metadata.get('timestamp', 'Unknown')
    
    # Extract per-proof-type statistics for ALL supported proof types
    # (dns_rsa + uri_rsa for v2; dns_familyid_ed25519 + uri_familyid_ed25519
    # for v3). Loop over PROOF_TYPE_STAT_KEYS so adding a future proof
    # type is one constant line, not 3 lines of extraction per type.
    proof_types = statistics.get('proof_types', {})
    for stat_key in PROOF_TYPE_STAT_KEYS:
        type_stats = proof_types.get(stat_key, {})
        metrics[f'{stat_key}_total'] = type_stats.get('total', 0)
        metrics[f'{stat_key}_valid'] = type_stats.get('valid', 0)
        metrics[f'{stat_key}_success_rate'] = type_stats.get('success_rate', 0.0)

    # Aggregate v2/v3 totals from the per-proof-type values just extracted.
    # This is what the dashboard's "v2 success rate" / "v3 success rate"
    # tiles read.
    metrics['v2_total'] = sum(
        metrics[f'{p.replace("-", "_")}_total'] for p in V2_PROOF_TYPES
    )
    metrics['v2_valid'] = sum(
        metrics[f'{p.replace("-", "_")}_valid'] for p in V2_PROOF_TYPES
    )
    metrics['v3_total'] = sum(
        metrics[f'{p.replace("-", "_")}_total'] for p in V3_PROOF_TYPES
    )
    metrics['v3_valid'] = sum(
        metrics[f'{p.replace("-", "_")}_valid'] for p in V3_PROOF_TYPES
    )
    metrics['v2_success_rate'] = _calc_percentage(metrics['v2_valid'], metrics['v2_total'])
    metrics['v3_success_rate'] = _calc_percentage(metrics['v3_valid'], metrics['v3_total'])

    # ciissversion adoption — passthrough of upstream stats when present.
    # ciissversion_declared: what relays declared in ContactInfo.
    # ciissversion_validated: what the validator actually processed.
    metrics['ciissversion_declared'] = statistics.get('ciissversion_declared', {}) or {}
    metrics['ciissversion_validated'] = statistics.get('ciissversion_validated', {}) or {}

    # v3 failure categories — already aggregated by upstream into 13
    # canonical categories. Pass through directly so the dashboard's
    # error-rollup table reads them without re-deriving.
    metrics['v3_failure_categories'] = statistics.get('v3_failure_categories', {}) or {}

    # A.8 build-time observability: warn once when upstream reports an
    # error_category we don't have a V3_CATEGORY_LABELS entry for.
    _warn_unknown_error_categories(metrics['v3_failure_categories'])
    
    # Build fingerprint -> validation result mapping for O(1) lookup
    validation_map = {}
    for result in validation_data.get('results', []):
        fingerprint = result.get('fingerprint')
        if fingerprint:
            validation_map[fingerprint] = result
    
    # Initialize operator-level tracking (if requested)
    unique_aroi_domains = set()
    domain_has_valid_relay = {}
    domain_relays = {}
    domain_failure_reasons = {}
    domain_country = {}  # Track country for each validated domain
    operator_error_domains = defaultdict(set)
    
    # SINGLE PASS: Process each relay for BOTH relay-level AND operator-level metrics
    for relay in relays:
        category = _categorize_relay_by_validation(relay, validation_map)
        
        # Relay-level counting
        if category == 'validated':
            metrics['aroi_validated_count'] += 1
        elif category == 'unvalidated':
            metrics['aroi_unvalidated_count'] += 1
        elif category == 'no_proof':
            metrics['aroi_no_proof_count'] += 1
        elif category == 'no_domain':
            metrics['aroi_no_domain_count'] += 1
        elif category == 'no_ciissversion':
            metrics['aroi_no_ciissversion_count'] += 1
        elif category == 'no_contact':
            metrics['relays_no_contact'] += 1
        elif category == 'no_aroi_info':
            metrics['relays_no_aroi_info'] += 1
        elif category == 'missing_two_aroi':
            metrics['relays_missing_two_aroi'] += 1
        elif category == 'version_proof_mismatch':
            metrics['relays_version_proof_mismatch'] += 1
        elif category == 'v3_informational':
            metrics['relays_v3_informational'] += 1
        
        # Operator-level tracking (in same loop for efficiency)
        if calculate_operator_metrics:
            aroi_domain = relay.get('aroi_domain', 'none')
            
            # Only track operators with all 3 required AROI fields (ciissversion:2, proof, url)
            # aroi_domain is only set if _simple_aroi_parsing found all 3 fields
            if aroi_domain and aroi_domain != 'none':
                unique_aroi_domains.add(aroi_domain)
                
                if aroi_domain not in domain_has_valid_relay:
                    domain_has_valid_relay[aroi_domain] = False
                    domain_relays[aroi_domain] = []
                    domain_failure_reasons[aroi_domain] = {}
                
                # Track country for this domain (use first relay's country)
                # relay["country"] is already UPPERCASE from _preprocess_template_data()
                if aroi_domain not in domain_country:
                    country = relay.get('country', 'unknown')
                    if country and country != 'unknown':
                        domain_country[aroi_domain] = country
                
                fp = relay.get('fingerprint')
                domain_relays[aroi_domain].append(fp)
                
                # Check validation status
                if fp in validation_map:
                    result = validation_map[fp]
                    if result.get('valid', False):
                        domain_has_valid_relay[aroi_domain] = True
                    else:
                        error = result.get('error', 'Unknown error')
                        # Only track actual validation failures, not missing AROI fields
                        # (relays with "Missing AROI fields" shouldn't have aroi_domain set, but defensive check)
                        if error not in ('Missing AROI fields', 'No contact information'):
                            domain_failure_reasons[aroi_domain][error] = domain_failure_reasons[aroi_domain].get(error, 0) + 1

    # Phase 2.1: Calculate percentages ONCE after the per-relay loop
    # completes (previously these were inside the loop, computed
    # ~10,867 times per build = ~108k redundant _calc_percentage calls).
    # Counts are stable after the loop; no reason to recompute on every
    # iteration. Net: O(N) → O(1) for percentage calculation.
    metrics['aroi_validated_percentage'] = _calc_percentage(metrics['aroi_validated_count'], total_relays)
    metrics['aroi_unvalidated_percentage'] = _calc_percentage(metrics['aroi_unvalidated_count'], total_relays)
    metrics['aroi_no_proof_percentage'] = _calc_percentage(metrics['aroi_no_proof_count'], total_relays)
    metrics['aroi_no_domain_percentage'] = _calc_percentage(metrics['aroi_no_domain_count'], total_relays)
    metrics['aroi_no_ciissversion_percentage'] = _calc_percentage(metrics['aroi_no_ciissversion_count'], total_relays)
    metrics['relays_no_contact_percentage'] = _calc_percentage(metrics['relays_no_contact'], total_relays)
    metrics['relays_no_aroi_info_percentage'] = _calc_percentage(metrics['relays_no_aroi_info'], total_relays)
    metrics['relays_missing_two_aroi_percentage'] = _calc_percentage(metrics['relays_missing_two_aroi'], total_relays)
    metrics['relays_version_proof_mismatch_percentage'] = _calc_percentage(metrics['relays_version_proof_mismatch'], total_relays)
    metrics['relays_v3_informational_percentage'] = _calc_percentage(metrics['relays_v3_informational'], total_relays)

    # Build no_aroi_reasons_top5 from the category counts
    no_aroi_reasons = [
        ("No contact info", metrics['relays_no_contact']),
        ("No AROI info", metrics['relays_no_aroi_info']),
        ("Missing 2 AROI fields", metrics['relays_missing_two_aroi']),
        ("Missing proof field (has domain + ciissversion)", metrics['aroi_no_proof_count']),
        ("Missing domain/URL field (has proof + ciissversion)", metrics['aroi_no_domain_count']),
        ("Missing ciissversion (has proof + domain)", metrics['aroi_no_ciissversion_count']),
    ]
    # Filter out zero counts and sort by count descending
    metrics['no_aroi_reasons_top5'] = sorted(
        [(reason, count) for reason, count in no_aroi_reasons if count > 0],
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    # Calculate overall validation success rate.
    # FIXED: previously this only summed v2 totals (dns_rsa + uri_rsa),
    # silently ignoring v3 (dns_familyid_ed25519 + uri_familyid_ed25519).
    # That made the metric meaningless once any operator had v3 relays.
    # Now it sums ALL four proof types so the rate reflects the whole
    # AROI-attempting population.
    total_aroi_attempts = sum(
        metrics.get(f'{pt}_total', 0) for pt in PROOF_TYPE_STAT_KEYS
    )
    total_aroi_valid = sum(
        metrics.get(f'{pt}_valid', 0) for pt in PROOF_TYPE_STAT_KEYS
    )

    if total_aroi_attempts > 0:
        metrics['aroi_validation_success_rate'] = (total_aroi_valid / total_aroi_attempts * 100)
    else:
        # Use metadata success rate if available
        metrics['aroi_validation_success_rate'] = metadata.get('success_rate', 0.0)
    
    # Calculate operator-level metrics (if requested)
    if calculate_operator_metrics:
        # Count validated vs invalid domains
        validated_aroi_domains = sum(1 for has_valid in domain_has_valid_relay.values() if has_valid)
        invalid_aroi_domains = len(unique_aroi_domains) - validated_aroi_domains
        
        # Build error details from existing domain_failure_reasons (already populated in main loop)
        relay_errors = {}  # error -> relay count
        
        # Process failed operators to get both relay and operator error counts
        for domain, has_valid in domain_has_valid_relay.items():
            if not has_valid:
                seen_simplified_errors = set()
                for error, relay_count in domain_failure_reasons.get(domain, {}).items():
                    relay_errors[error] = relay_errors.get(error, 0) + relay_count
                    simplified_error, _ = _simplify_error_message(error)
                    if simplified_error not in seen_simplified_errors:
                        operator_error_domains[simplified_error].add(domain)
                        seen_simplified_errors.add(simplified_error)
        
        # Simplify error messages and categorize by proof type
        simplified_relay_errors = _simplify_and_categorize_errors(relay_errors)
        
        # Store top 5 for general tooltips (simplified messages)
        metrics['relay_error_top5'] = sorted(simplified_relay_errors['all'].items(), key=lambda x: x[1], reverse=True)[:5]
        metrics['operator_error_top5'] = sorted(
            ((reason, len(domains)) for reason, domains in operator_error_domains.items()),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Store categorized top 5 for DNS-RSA and URI-RSA tooltips
        metrics['dns_error_top5'] = sorted(simplified_relay_errors['dns'].items(), key=lambda x: x[1], reverse=True)[:5]
        metrics['uri_error_top5'] = sorted(simplified_relay_errors['uri'].items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Calculate top operators by relay count
        domain_relay_counts = [(domain, len(fps)) for domain, fps in domain_relays.items()]
        domain_relay_counts.sort(key=lambda x: x[1], reverse=True)
        top_ops = [f"{domain} ({count:,} relays)" for domain, count in domain_relay_counts[:4]]
        top_operators_text = ", ".join(top_ops) if top_ops else "No data available"
        
        # Add operator metrics
        metrics['unique_aroi_domains_count'] = len(unique_aroi_domains)
        metrics['validated_aroi_domains_count'] = validated_aroi_domains
        metrics['invalid_aroi_domains_count'] = invalid_aroi_domains
        
        if len(unique_aroi_domains) > 0:
            metrics['validated_aroi_domains_percentage'] = (validated_aroi_domains / len(unique_aroi_domains) * 100)
            metrics['invalid_aroi_domains_percentage'] = (invalid_aroi_domains / len(unique_aroi_domains) * 100)
        else:
            metrics['validated_aroi_domains_percentage'] = 0.0
            metrics['invalid_aroi_domains_percentage'] = 0.0
        
        metrics['top_operators_text'] = top_operators_text
        
        # Build validated domain set once for both IPv6 and country calculations
        validated_domains = {d for d, valid in domain_has_valid_relay.items() if valid}
        metrics['_validated_domain_set'] = validated_domains
        
        # Calculate top 3 countries by validated AROI operator count
        country_counts = {}
        for domain in validated_domains:
            if domain in domain_country:
                country_counts[domain_country[domain]] = country_counts.get(domain_country[domain], 0) + 1
        
        # Sort and format top 3 for template
        metrics['top_3_aroi_countries'] = [
            {'rank': i, 'country_code': cc, 'count': cnt, 
             'percentage': (cnt / validated_aroi_domains * 100) if validated_aroi_domains > 0 else 0.0}
            for i, (cc, cnt) in enumerate(sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:3], 1)
        ]
    
    # Store validation_map for reuse by contact pages (avoids rebuilding 3,000+ times)
    metrics['_validation_map'] = validation_map

    # A.6: consolidated v2/v3 error rollup keyed by upstream error_category.
    # Templates render this as 3 sections (shared / v2-only / v3-only) so
    # operators see "X common errors apply to both versions; Y are v2-only;
    # Z are v3-only" without having to mentally cross-reference.
    shared_rollup, v2_rollup, v3_rollup = _build_error_rollup(
        validation_data.get('results', []) if validation_data else []
    )
    metrics['error_rollup_shared'] = shared_rollup
    metrics['error_rollup_v2_only'] = v2_rollup
    metrics['error_rollup_v3_only'] = v3_rollup

    return metrics


def _format_timestamp(timestamp_str):
    """Format ISO timestamp to human-readable format."""
    if not timestamp_str:
        return 'Unknown'
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M UTC')
    except (ValueError, AttributeError):
        return timestamp_str


def get_contact_validation_status(relays: List[Dict], validation_data: Optional[Dict] = None, validation_map: Optional[Dict] = None) -> Dict:
    """
    Get AROI validation status for a specific contact's relays (v2 + v3 aware).

    Cascade logic (highest-precedence label first; ties picked top-down):
      - validated:     >=1 relay passes upstream validation
      - unauthorized:  0 validated AND >=1 dns/uri content_mismatch
                       (relay claims domain but proof says it doesn't)
      - misconfigured: 0 validated AND 0 unauthorized AND >=1 transport
                       error / SSL / etc.
      - incomplete:    0 validated AND 0 unauthorized/misconfigured AND
                       >=1 relay missing 1-2 AROI fields
      - not_configured: all relays have 0 AROI fields

    NEW peer issue categories (added to plain operator pages alongside the
    cascade categories — they do NOT change top-level validation_status):
      - security_incident_relays: error_category=='secret_key_leaked'
      - pending_onionoo_relays:   error_category=='missing_family_ids'
                                  (operator changed torrc but Onionoo
                                   hasn't refreshed family_ids yet)

    NEW operator-level migration metadata:
      - is_mixed_migration: True iff operator has BOTH v2 AND v3 declaring
                            relays under the same contact
      - v3_relay_count / v2_relay_count / v3_pct_of_total /
        v3_migration_progress_pct
      - v3_tier: 'none'|'explorer'|'migrating'|'mostly'|'complete'
        (consumed by leaderboards, listing icons, and the operator
         header pill in B1)
      - is_v3_adopter: v3 share of total relays >= V3_LISTING_ICON_THRESHOLD

    A.4 changes: when val_result['error_category'] is set, prefer it over
    today's substring heuristic for cascade decisions; passthrough the
    upstream `hint` field so templates can render pasteable fix copy
    inline.

    Args:
        relays: List of relay dictionaries for this contact
        validation_data: Optional validation data from aroivalidator.1aeo.com
        validation_map: Optional pre-built fingerprint -> validation result
            map (avoids rebuilding 3,000+ times)
    """
    result = {
        'has_aroi': False,
        'validation_status': 'not_configured',  # validated | unauthorized | misconfigured | incomplete | not_configured

        # Complete AROI relays (all 3 fields present, version+proof match)
        'validated_relays': [],
        'unauthorized_relays': [],    # dns/uri content_mismatch
        'misconfigured_relays': [],   # SSL / timeout / 404 / transport

        # Incomplete AROI relays (1-2 fields)
        'incomplete_relays': [],
        # No AROI relays (0 fields)
        'not_configured_relays': [],

        # NEW peer issue categories (A.5): rendered alongside the cascade,
        # NOT replacing it. Empty when count == 0.
        'security_incident_relays': [],
        'pending_onionoo_relays': [],

        # Fingerprint sets for O(1) lookups in templates
        'validated_fingerprints': set(),
        'unauthorized_fingerprints': set(),
        'misconfigured_fingerprints': set(),
        'security_incident_fingerprints': set(),
        'pending_onionoo_fingerprints': set(),

        'validation_summary': {
            'total_relays': len(relays),
            'validated_count': 0,
            'unauthorized_count': 0,
            'misconfigured_count': 0,
            'incomplete_count': 0,
            'not_configured_count': 0,
            # NEW: peer-category counts
            'security_incident_count': 0,
            'pending_onionoo_count': 0,
            # NEW: operator-level v2/v3 migration tally
            'v2_relay_count': 0,
            'v3_relay_count': 0,
            'v3_pct_of_total': 0.0,
            'v3_migration_progress_pct': 0.0,
            'is_mixed_migration': False,
            'is_v3_adopter': False,
            'v3_tier': 'none',      # none|explorer|migrating|mostly|complete
            # B1.1 (final): per-version validated counts for the
            # success-rate pills in the v3_migration_summary section.
            'v2_validated_count': 0,
            'v3_validated_count': 0,
            'v2_success_rate': 0.0,
            'v3_success_rate': 0.0,
            # Granular counts for troubleshooting tooltips
            'incomplete_no_proof_count': 0,
            'incomplete_no_domain_count': 0,
            'incomplete_no_ciissversion_count': 0,
            'incomplete_missing_two_count': 0,
            'incomplete_version_proof_mismatch_count': 0,
            'incomplete_v3_informational_count': 0,
            'not_configured_no_aroi_info_count': 0,
            'not_configured_no_contact_count': 0,
        },
        'validation_available': False,
        'show_detailed_errors': True,
    }
    
    if not relays:
        return result
    
    # Use pre-built validation_map if provided (much faster - avoids rebuilding map 3,000+ times)
    if validation_map is None:
        # FALLBACK: Build fingerprint -> validation result mapping
        validation_map = {}
        if validation_data and 'results' in validation_data:
            for val_result in validation_data.get('results', []):
                fingerprint = val_result.get('fingerprint')
                if fingerprint:
                    validation_map[fingerprint] = val_result
            result['validation_available'] = True
    else:
        result['validation_available'] = len(validation_map) > 0
    
    # Single pass through relays - categorize each one
    summary = result['validation_summary']
    for relay in relays:
        fingerprint = relay.get('fingerprint')
        aroi_domain = relay.get('aroi_domain', 'none')
        # New per-relay fields from A.2.1 (set by _simple_aroi_parsing).
        relay_aroi_version = relay.get('aroi_version')
        relay_aroi_proof_type = relay.get('aroi_proof_type')
        nickname = relay.get('nickname', 'Unnamed')
        contact = relay.get('contact', '')
        first_seen = relay.get('first_seen', 'Unknown')

        # A.5 operator-level v2/v3 tally (any AROI-declaring relay
        # contributes, even if validation fails).
        if relay_aroi_version == '2':
            summary['v2_relay_count'] += 1
        elif relay_aroi_version == '3':
            summary['v3_relay_count'] += 1

        # Check if relay has complete AROI setup (all 3 fields, consistent
        # version+proof). aroi_domain is "none" when _simple_aroi_parsing
        # detected a mismatch, so this also rejects copy-paste errors.
        has_complete_aroi = aroi_domain and aroi_domain != 'none'

        if has_complete_aroi:
            # Relay has all 3 AROI fields - check upstream validation result
            result['has_aroi'] = True

            if fingerprint not in validation_map:
                # Has AROI but not in validation data - treat as misconfigured
                # (unknown status, often a brand-new relay).
                summary['misconfigured_count'] += 1
                result['misconfigured_relays'].append({
                    'fingerprint': fingerprint,
                    'nickname': nickname,
                    'aroi_domain': aroi_domain,
                    'error': 'Not yet processed by validator (relay may be new)',
                    'proof_type': relay_aroi_proof_type or 'unknown',
                    'aroi_version': relay_aroi_version,
                    'first_seen': first_seen,
                    'relay': relay,
                    'hint': None,
                    'error_category': None,
                })
                continue

            val_result = validation_map[fingerprint]

            if val_result.get('valid', False):
                # VALIDATED: upstream validation passed.
                summary['validated_count'] += 1
                # B1.1 (final): per-version validated tally for success-rate pills.
                _val_version = val_result.get('ciissversion') or relay_aroi_version
                if _val_version == '2':
                    summary['v2_validated_count'] += 1
                elif _val_version == '3':
                    summary['v3_validated_count'] += 1
                result['validated_relays'].append({
                    'fingerprint': fingerprint,
                    'nickname': nickname,
                    'aroi_domain': aroi_domain,
                    'proof_type': val_result.get('proof_type') or relay_aroi_proof_type or 'unknown',
                    'proof_uri': val_result.get('proof_uri', ''),
                    'aroi_version': _val_version,
                    'first_seen': first_seen,
                    'relay': relay,
                })
                continue

            # Validation failed -> categorize by error_category (A.4) with
            # fallback to substring heuristic (older cached pre-schema-v2
            # responses don't have error_category).
            error = val_result.get('error', 'Unknown error')
            error = _deduplicate_fingerprint_not_found_error(error)
            error_category = val_result.get('error_category')

            # B-final: surface V3_CATEGORY_LABELS pasteable example as
            # 'pasteable_example' alongside the upstream `hint` so the
            # template can render BOTH:
            #   - upstream hint (current best guidance, may be prose)
            #   - our pasteable example (single line, copy-paste-able)
            # This strengthens the pasteable-examples contract from the
            # plan: operators always see at least one literally-pasteable
            # line, even when upstream hint is mostly prose.
            _label = (V3_CATEGORY_LABELS.get(error_category) or {}) if error_category else {}
            # The relay's actual proof_type drives version-aware example
            # selection (URI-RSA → rsa-fingerprint.txt, URI-FamilyID-Ed25519
            # → ed25519-family-id.txt). User-reported bug fix:
            # "URI-RSA fingerprint not found" was rendering the v3 file
            # path because the example was hard-coded to ed25519.
            _resolved_proof_type = (
                val_result.get('proof_type') or relay_aroi_proof_type or 'unknown'
            )
            relay_info = {
                'fingerprint': fingerprint,
                'nickname': nickname,
                'aroi_domain': aroi_domain,
                'error': error,
                'proof_type': _resolved_proof_type,
                'aroi_version': val_result.get('ciissversion') or relay_aroi_version,
                'first_seen': first_seen,
                'relay': relay,
                # A.4: pass through upstream's actionable hint verbatim.
                'hint': val_result.get('hint'),
                'error_category': error_category,
                # B-final: pasteable one-line example from V3_CATEGORY_LABELS.
                # Distinct from `hint` (which may be prose). Templates render
                # this as a code block when present.
                # UX-fix: substitute <fingerprint> / <your-domain> with this
                # relay's actual values so the operator can copy-paste
                # the line verbatim and run it without manual editing.
                'pasteable_example': _render_pasteable_example(
                    _resolve_example_for_proof(_label, _resolved_proof_type),
                    fingerprint, aroi_domain
                ),
            }

            # A.5: peer issue categories — first because they should appear
            # alongside the cascade, not be hidden by it.
            if error_category == 'secret_key_leaked':
                summary['security_incident_count'] += 1
                result['security_incident_relays'].append(relay_info)
                # secret_key_leaked is also a misconfiguration; surface it
                # in the cascade-misconfigured list so the operator status
                # cascade reflects "something is wrong" (not "validated").
                summary['misconfigured_count'] += 1
                result['misconfigured_relays'].append(relay_info)
                continue
            if error_category == 'missing_family_ids':
                # Onionoo lag — actionable but transient. Bucket as
                # peer "pending" AND in the cascade as misconfigured
                # so cascade still detects the operator has issues.
                summary['pending_onionoo_count'] += 1
                result['pending_onionoo_relays'].append(relay_info)
                summary['misconfigured_count'] += 1
                result['misconfigured_relays'].append(relay_info)
                continue

            # A.4: prefer error_category for cascade decisions; fall back
            # to today's substring heuristic when the category is absent.
            if error_category in ('uri_content_mismatch', 'dns_content_mismatch'):
                is_unauthorized = True
            elif error_category is not None:
                is_unauthorized = False
            else:
                # Pre-schema-v2 fallback heuristic (preserved verbatim).
                error_lower = error.lower()
                is_http_error = '404' in error_lower or 'http error' in error_lower
                is_unauthorized = (
                    not is_http_error and (
                        'fingerprint not found' in error_lower or
                        ('not found' in error_lower and ('dns' in error_lower or 'txt' in error_lower or 'record' in error_lower) and 'nxdomain' not in error_lower)
                    )
                )

            if is_unauthorized:
                summary['unauthorized_count'] += 1
                result['unauthorized_relays'].append(relay_info)
            else:
                summary['misconfigured_count'] += 1
                result['misconfigured_relays'].append(relay_info)
        else:
            # Relay does NOT have complete AROI - categorize as incomplete or not_configured
            aroi_fields = _check_aroi_fields(contact)
            has_contact = bool(contact and contact.strip())
            category = _categorize_by_missing_fields(aroi_fields, has_contact)
            
            relay_info = {
                'fingerprint': fingerprint,
                'nickname': nickname,
                'aroi_domain': aroi_domain if aroi_domain != 'none' else None,
                'contact': contact,
                'first_seen': first_seen,
                'category': category,
                'relay': relay,
            }
            
            if category in ('no_contact',):
                # Not configured: no contact at all
                summary['not_configured_count'] += 1
                summary['not_configured_no_contact_count'] += 1
                relay_info['missing'] = 'No contact info'
                result['not_configured_relays'].append(relay_info)
            elif category == 'no_aroi_info':
                # Not configured: has contact but no AROI fields
                summary['not_configured_count'] += 1
                summary['not_configured_no_aroi_info_count'] += 1
                relay_info['missing'] = 'Has contact, no AROI fields'
                result['not_configured_relays'].append(relay_info)
            elif category == 'v3_informational':
                # CIISS v3 spec-legal: ciissversion:3 with informational
                # fields and no url. NOT incomplete; treat as
                # "not_configured" because there's no domain claim to
                # validate against.
                #
                # Reviewer-flagged: a v3_informational relay HAS declared
                # ciissversion:3 — it is NOT a zero-AROI-field contact.
                # Set result['has_aroi'] = True so downstream code that
                # filters on 'operators with any AROI declaration' sees
                # these relays. Drop the not_configured_no_aroi_info_count
                # bump (that bucket is reserved for relays with NO AROI
                # fields at all). Keep the not_configured_count and
                # incomplete_v3_informational_count bumps so the cascade
                # still flags 'no domain claim to validate' but the
                # dedicated counter accurately reflects v3-informational.
                result['has_aroi'] = True
                summary['not_configured_count'] += 1
                summary['incomplete_v3_informational_count'] += 1
                relay_info['missing'] = (
                    "ciissversion:3 with no url (spec-legal informational only)"
                )
                # Surface the pasteable-example hint for operators who
                # actually wanted a domain-bound AROI.
                v3_info_label = V3_CATEGORY_LABELS.get('v3_informational', {})
                _v3i_example = _render_pasteable_example(
                    v3_info_label.get('example'), fingerprint, aroi_domain
                )
                relay_info['hint'] = _v3i_example
                relay_info['pasteable_example'] = _v3i_example
                relay_info['error_category'] = 'v3_informational'
                result['not_configured_relays'].append(relay_info)
            else:
                # Incomplete: 1-2 AROI fields, OR version/proof mismatch
                result['has_aroi'] = True
                summary['incomplete_count'] += 1

                if category == 'no_proof':
                    summary['incomplete_no_proof_count'] += 1
                    relay_info['missing'] = 'Missing proof field (has domain + ciissversion)'
                elif category == 'no_domain':
                    summary['incomplete_no_domain_count'] += 1
                    relay_info['missing'] = 'Missing domain/URL field (has proof + ciissversion)'
                elif category == 'no_ciissversion':
                    summary['incomplete_no_ciissversion_count'] += 1
                    relay_info['missing'] = 'Missing ciissversion (has proof + domain)'
                elif category == 'missing_two_aroi':
                    summary['incomplete_missing_two_count'] += 1
                    missing_fields = []
                    if not aroi_fields['has_proof']:
                        missing_fields.append('proof')
                    if not aroi_fields['has_url']:
                        missing_fields.append('url/domain')
                    if not aroi_fields['has_ciissversion']:
                        missing_fields.append('ciissversion')
                    relay_info['missing'] = f"Missing {' and '.join(missing_fields)}"
                elif category == 'version_proof_mismatch':
                    # Operator copy-paste error during migration. All 3
                    # fields present but proof type doesn't match declared
                    # ciissversion. Surface pasteable fix.
                    summary['incomplete_version_proof_mismatch_count'] += 1
                    relay_info['missing'] = (
                        f"ciissversion:{aroi_fields.get('version')} declared but "
                        f"proof:{aroi_fields.get('proof_type')} is for the "
                        f"other version"
                    )
                    mismatch_label = V3_CATEGORY_LABELS.get('version_proof_mismatch', {})
                    _vpm_example = _render_pasteable_example(
                        mismatch_label.get('example'), fingerprint, aroi_domain
                    )
                    relay_info['hint'] = _vpm_example
                    relay_info['pasteable_example'] = _vpm_example
                    relay_info['error_category'] = 'version_proof_mismatch'
                else:
                    relay_info['missing'] = 'Incomplete AROI configuration'

                result['incomplete_relays'].append(relay_info)
    
    # Determine operator status using cascade logic. The peer issue
    # categories (security_incident, pending_onionoo) DO NOT take
    # precedence; they're rendered alongside whatever the cascade picks
    # so a v3 operator with 1 leaked-key relay still gets "validated"
    # cascade if their other relays validated. Templates are responsible
    # for surfacing the peer alerts independently.
    if summary['validated_count'] > 0:
        result['validation_status'] = 'validated'
    elif summary['unauthorized_count'] > 0:
        result['validation_status'] = 'unauthorized'
    elif summary['misconfigured_count'] > 0:
        result['validation_status'] = 'misconfigured'
    elif summary['incomplete_count'] > 0:
        result['validation_status'] = 'incomplete'
    else:
        result['validation_status'] = 'not_configured'

    # A.5 operator-level migration metadata. Computed once, consumed by
    # every B-phase surface (operator pill, leaderboard tier, search
    # index, listing icons).
    # Two explicitly-named percentages (the old ambiguous
    # v3_relay_percentage mixed denominators between surfaces):
    # - v3_pct_of_total: share of ALL the operator's relays on v3; matches
    #   v3_tier / is_v3_adopter and the contact-page "(N of TOTAL)" copy.
    # - v3_migration_progress_pct: share of AROI-DECLARING relays on v3;
    #   drives the mixed-migration pill only.
    total_aroi_relays = summary['v2_relay_count'] + summary['v3_relay_count']
    if summary['total_relays'] > 0:
        summary['v3_pct_of_total'] = (
            summary['v3_relay_count'] / summary['total_relays'] * 100
        )
    if total_aroi_relays > 0:
        summary['v3_migration_progress_pct'] = (
            summary['v3_relay_count'] / total_aroi_relays * 100
        )
    summary['is_mixed_migration'] = (
        summary['v2_relay_count'] > 0 and summary['v3_relay_count'] > 0
    )
    # Tier classification uses TOTAL relay count so 1-of-50 is "explorer"
    # not "complete" (matches plan's intent: recognise scale of effort).
    summary['v3_tier'] = classify_v3_tier(
        summary['v3_relay_count'], summary['total_relays']
    )
    summary['is_v3_adopter'] = (
        summary['total_relays'] > 0
        and summary['v3_relay_count'] / summary['total_relays']
        >= V3_LISTING_ICON_THRESHOLD
    )
    # B1.1 (final): per-version success rates for v3_migration_summary
    # success-rate pills. Mirrors the network-wide v2_success_rate /
    # v3_success_rate emitted in the dashboard but at operator scope.
    summary['v2_success_rate'] = _calc_percentage(
        summary['v2_validated_count'], summary['v2_relay_count']
    )
    summary['v3_success_rate'] = _calc_percentage(
        summary['v3_validated_count'], summary['v3_relay_count']
    )

    # Build fingerprint sets for O(1) lookups in templates
    result['validated_fingerprints'] = {r['fingerprint'] for r in result['validated_relays']}
    result['unauthorized_fingerprints'] = {r['fingerprint'] for r in result['unauthorized_relays']}
    result['misconfigured_fingerprints'] = {r['fingerprint'] for r in result['misconfigured_relays']}
    result['security_incident_fingerprints'] = {r['fingerprint'] for r in result['security_incident_relays']}
    result['pending_onionoo_fingerprints'] = {r['fingerprint'] for r in result['pending_onionoo_relays']}

    return result
