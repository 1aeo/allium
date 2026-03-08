"""
File: contact_sorting.py

Pure contact-page sorting logic: constants, sort-key helpers, and variant
builders for static no-JS column-header sorting on contact operator pages.

This module is intentionally free of page_writer/Jinja2/multiprocessing
dependencies so it can be unit-tested in isolation and imported without
circular references.
"""

import ipaddress as _ipaddress
from datetime import datetime as _dt

from .flag_analysis import FLAG_PRIORITY as _FLAG_PRIORITY
from .ip_utils import safe_parse_ip_address as _safe_parse_ip_address

# =============================================================================
# CONSTANTS
# =============================================================================

CONTACT_SORT_FILE_MAP = {
    'status': 'by-status.html',
    'nickname': 'by-nickname.html',
    'bandwidth': 'index.html',  # default mode, intentionally no by-bandwidth.html
    'total_data': 'by-total-data.html',
    'uptime': 'by-uptime.html',
    'uptime_percentage': 'by-uptime-percentage.html',
    'flag_uptime': 'by-flag-uptime.html',
    'ipv4': 'by-ipv4.html',
    'flags': 'by-flags.html',
    'dns': 'by-dns.html',
    'family': 'by-family.html',
    'country': 'by-country.html',
    'as_number': 'by-as-number.html',
    'as_name': 'by-as-name.html',
    'platform': 'by-platform.html',
    'first_seen': 'by-first-seen.html',
    'last_restarted': 'by-last-restarted.html',
    'ipv6': 'by-ipv6.html',
}

CONTACT_SORT_MODES = tuple(CONTACT_SORT_FILE_MAP.keys())
CONTACT_DEFAULT_SORT_MODE = 'bandwidth'

CONTACT_SECTION_KEYS = (
    'validated_relays',
    'misconfigured_relays',
    'unauthorized_relays',
    'incomplete_relays',
    'not_configured_relays',
)

TOTAL_DATA_PERIOD_ORDER = ('5_years', '1_year', '6_months', '1_month')
DNS_SORT_RANK = {'success': 0, 'fail': 1, 'untested': 2}
FAMILY_SORT_RANK = {'both': 0, 'happy_families': 1, 'my_family': 2, 'none': 3}


# =============================================================================
# VANITY PATH HELPER
# =============================================================================

def adjust_vanity_paths(rendered_html: str) -> str:
    """Adjust relative paths when copying contact pages to vanity root."""
    return rendered_html.replace('href="../../', 'href="../').replace('src="../../', 'src="../')


def contact_sort_links():
    """Return static link map used by contact page sortable headers."""
    return CONTACT_SORT_FILE_MAP


# =============================================================================
# SORT KEY HELPERS (pure functions)
# =============================================================================

def parse_epoch(ts):
    """Parse allium timestamp strings into unix epoch for deterministic sorting."""
    if not ts:
        return None
    try:
        return _dt.strptime(ts, '%Y-%m-%d %H:%M:%S').timestamp()
    except (TypeError, ValueError):
        return None


def safe_lower(value):
    """Lowercase string conversion with None handling."""
    return str(value or '').lower()


def best_total_data_bytes(relay):
    """Return best-available total data bytes using period fallback chain."""
    td = relay.get('total_data') or {}
    for period in TOTAL_DATA_PERIOD_ORDER:
        value = td.get(period, 0)
        if value and value > 0:
            return value
    return 0


def extract_ipv4_numeric(relay):
    """Extract first IPv4 address as packed bytes for numeric sort ordering."""
    for addr in relay.get('or_addresses') or []:
        parsed_ip, _ = _safe_parse_ip_address(addr)
        if parsed_ip and '.' in parsed_ip:
            try:
                return _ipaddress.ip_address(parsed_ip).packed
            except (ValueError, TypeError):
                pass
    return None


def extract_ipv6_numeric(relay):
    """Extract first IPv6 address as packed bytes for numeric sort ordering."""
    for addr in relay.get('or_addresses') or []:
        if ':' in addr and addr.count(':') > 1:
            ip_str = addr.split(']')[0].lstrip('[')
            try:
                return _ipaddress.ip_address(ip_str).packed
            except (ValueError, TypeError):
                pass
    return None


def prioritized_flag_uptime_6m(relay):
    """Return 6-month uptime for the relay's prioritized *current* flag.

    Must mirror the display-layer flag selection in flag_analysis.py:
    only consider flags the relay currently has (Exit > Guard > Fast > Running).
    """
    relay_flags = set(relay.get('flags', []))
    flag_data = relay.get('_flag_uptime_data') or {}
    if not flag_data or not relay_flags:
        return -1.0

    selected_flag = None
    best_priority = float('inf')
    for flag in flag_data.keys():
        # Only consider flags the relay CURRENTLY has (mirrors display logic)
        if flag in relay_flags:
            priority = _FLAG_PRIORITY.get(flag)
            if priority and priority < best_priority:
                best_priority = priority
                selected_flag = flag

    if not selected_flag:
        return -1.0

    period_data = flag_data.get(selected_flag, {}).get('6_months')
    if isinstance(period_data, dict):
        uptime = period_data.get('uptime')
        if isinstance(uptime, (int, float)):
            return float(uptime)
    return -1.0


def as_number_sort_value(relay):
    """Parse AS number for numeric sorting. Unknown/missing → end."""
    relay_as = relay.get('as')
    if not relay_as:
        return (1, float('inf'))
    relay_as = str(relay_as).upper()
    if relay_as.startswith('AS'):
        relay_as = relay_as[2:]
    try:
        return (0, int(relay_as))
    except ValueError:
        return (1, float('inf'))


def uptime_column_sort_key(relay):
    """Sort key for uptime/downtime column: running first, longest uptime first."""
    running = relay.get('running', False)
    restart_epoch = parse_epoch(relay.get('last_restarted'))
    last_seen_epoch = parse_epoch(relay.get('last_seen'))

    if running:
        return (0, restart_epoch if restart_epoch is not None else float('inf'), 0)

    # Offline relays: newer last_seen first (smaller key via negative)
    return (1, float('inf'), -(last_seen_epoch if last_seen_epoch is not None else -1))


def relay_sort_key(relay, sort_mode):
    """Deterministic sort key for a relay dict, dispatched by sort_mode.

    All modes use fingerprint as final tie-breaker for stable ordering.
    """
    fingerprint = relay.get('fingerprint', '')

    if sort_mode == 'status':
        return (0 if relay.get('running') else 1, safe_lower(relay.get('nickname')), fingerprint)
    if sort_mode == 'nickname':
        return (safe_lower(relay.get('nickname')), fingerprint)
    if sort_mode == 'bandwidth':
        return (-int(relay.get('observed_bandwidth', 0) or 0), fingerprint)
    if sort_mode == 'total_data':
        return (-best_total_data_bytes(relay), fingerprint)
    if sort_mode == 'uptime':
        return (*uptime_column_sort_key(relay), fingerprint)
    if sort_mode == 'uptime_percentage':
        percentages = relay.get('uptime_percentages') or {}
        return (
            -float(percentages.get('6_months', 0.0)),
            -float(percentages.get('1_month', 0.0)),
            -float(percentages.get('1_year', 0.0)),
            -float(percentages.get('5_years', 0.0)),
            fingerprint,
        )
    if sort_mode == 'flag_uptime':
        return (-prioritized_flag_uptime_6m(relay), fingerprint)
    if sort_mode == 'ipv4':
        ip_packed = extract_ipv4_numeric(relay)
        return (0 if ip_packed else 1, ip_packed if ip_packed else b'\xff' * 4, fingerprint)
    if sort_mode == 'flags':
        flags = relay.get('flags') or []
        role_rank = 0 if 'Exit' in flags else 1 if 'Guard' in flags else 2
        return (role_rank, '|'.join(sorted(flags)), fingerprint)
    if sort_mode == 'dns':
        rank = DNS_SORT_RANK.get(relay.get('exit_dns_health_status'), 3)
        return (rank, safe_lower(relay.get('nickname')), fingerprint)
    if sort_mode == 'family':
        family_type = relay.get('family_support_type', 'none')
        family_len = len(relay.get('effective_family') or [])
        return (FAMILY_SORT_RANK.get(family_type, 4), -family_len, fingerprint)
    if sort_mode == 'country':
        return (safe_lower(relay.get('country')), safe_lower(relay.get('country_name')), fingerprint)
    if sort_mode == 'as_number':
        return (*as_number_sort_value(relay), fingerprint)
    if sort_mode == 'as_name':
        as_name = relay.get('as_name') or ''
        return (0 if as_name else 1, safe_lower(as_name), fingerprint)
    if sort_mode == 'platform':
        return (safe_lower(relay.get('platform')), fingerprint)
    if sort_mode == 'first_seen':
        epoch = parse_epoch(relay.get('first_seen'))
        return (-(epoch if epoch is not None else -1), fingerprint)
    if sort_mode == 'last_restarted':
        epoch = parse_epoch(relay.get('last_restarted'))
        return (-(epoch if epoch is not None else -1), 0 if epoch is not None else 1, fingerprint)
    if sort_mode == 'ipv6':
        ip6_packed = extract_ipv6_numeric(relay)
        return (0 if ip6_packed else 1, ip6_packed if ip6_packed else b'\xff' * 16, fingerprint)

    # Fallback: bandwidth descending
    return (-int(relay.get('observed_bandwidth', 0) or 0), fingerprint)


# =============================================================================
# PUBLIC SORT API
# =============================================================================

def sort_contact_relays(relays, sort_mode):
    """Sort plain relay dictionaries for contact single-table mode."""
    if not relays:
        return relays
    return sorted(relays, key=lambda relay: relay_sort_key(relay, sort_mode))


def sort_contact_section_entries(entries, sort_mode):
    """Sort wrapper dicts used by AROI sectioned contact tables."""
    if not entries:
        return entries
    return sorted(entries, key=lambda entry: relay_sort_key(entry.get('relay', {}), sort_mode))


def build_contact_variant_args(base_template_args, sort_mode):
    """Build per-variant template args from a shared contact-page base args dict."""
    variant_args = dict(base_template_args)
    variant_args['relay_subset'] = sort_contact_relays(base_template_args.get('relay_subset', []), sort_mode)
    variant_args['contact_sort_mode'] = sort_mode
    variant_args['contact_sort_links'] = contact_sort_links()
    variant_args['sortable_scope'] = 'contact'

    contact_validation_status = base_template_args.get('contact_validation_status')
    if isinstance(contact_validation_status, dict):
        status_copy = dict(contact_validation_status)
        for section_key in CONTACT_SECTION_KEYS:
            status_copy[section_key] = sort_contact_section_entries(
                contact_validation_status.get(section_key, []), sort_mode
            )
        variant_args['contact_validation_status'] = status_copy

    return variant_args
