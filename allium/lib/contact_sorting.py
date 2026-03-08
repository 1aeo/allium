"""
Contact-page relay sorting helpers.

Pure helpers/constants for static contact sort variants.
No template rendering, multiprocessing, or filesystem I/O.
"""

import ipaddress
from datetime import datetime as _dt

from .flag_analysis import FLAG_PRIORITY
from .ip_utils import safe_parse_ip_address as _safe_parse_ip_address

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


def _adjust_vanity_paths(rendered_html: str) -> str:
    """Adjust relative paths when copying contact pages to vanity root."""
    return rendered_html.replace('href="../../', 'href="../').replace('src="../../', 'src="../')


def _contact_sort_links(enabled_modes=None):
    """Return static link map used by contact page sortable headers."""
    modes = enabled_modes or CONTACT_SORT_MODES
    return {mode: CONTACT_SORT_FILE_MAP[mode] for mode in modes if mode in CONTACT_SORT_FILE_MAP}


def _parse_epoch(ts):
    """Parse allium timestamp strings into unix epoch for deterministic sorting."""
    if not ts:
        return None
    try:
        return _dt.strptime(ts, '%Y-%m-%d %H:%M:%S').timestamp()
    except (TypeError, ValueError):
        return None


def _safe_lower(value):
    return str(value or '').lower()


def _best_total_data_bytes(relay):
    td = relay.get('total_data') or {}
    for period in TOTAL_DATA_PERIOD_ORDER:
        value = td.get(period, 0)
        if value and value > 0:
            return value
    return 0


def _extract_ipv4(relay):
    for addr in relay.get('or_addresses') or []:
        parsed_ip, ip_version = _safe_parse_ip_address(addr)
        if parsed_ip and ip_version == 4:
            try:
                return ipaddress.ip_address(parsed_ip).packed
            except ValueError:
                return None
    return None


def _extract_ipv6(relay):
    for addr in relay.get('or_addresses') or []:
        parsed_ip, ip_version = _safe_parse_ip_address(addr)
        if parsed_ip and ip_version == 6:
            try:
                return ipaddress.ip_address(parsed_ip).packed
            except ValueError:
                return None
    return None


def _prioritized_flag_uptime_6m(relay):
    relay_flags = set(relay.get('flags', []))
    flag_data = relay.get('_flag_uptime_data') or {}
    if not flag_data or not relay_flags:
        return -1.0

    selected_flag = None
    best_priority = float('inf')
    for flag in flag_data.keys():
        priority = FLAG_PRIORITY.get(flag, float('inf'))
        if flag in relay_flags and priority < best_priority:
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


def _as_number_sort_value(relay):
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


def _uptime_column_sort_key(relay):
    running = relay.get('running', False)
    restart_epoch = _parse_epoch(relay.get('last_restarted'))
    last_seen_epoch = _parse_epoch(relay.get('last_seen'))

    if running:
        return (0, restart_epoch if restart_epoch is not None else float('inf'), 0)

    # Offline relays: newer last_seen first (smaller key via negative)
    return (1, float('inf'), -(last_seen_epoch if last_seen_epoch is not None else -1))


def _relay_sort_key(relay, sort_mode):
    fingerprint = relay.get('fingerprint', '')

    if sort_mode == 'status':
        return (0 if relay.get('running') else 1, _safe_lower(relay.get('nickname')), fingerprint)
    if sort_mode == 'nickname':
        return (_safe_lower(relay.get('nickname')), fingerprint)
    if sort_mode == 'bandwidth':
        return (-int(relay.get('observed_bandwidth', 0) or 0), fingerprint)
    if sort_mode == 'total_data':
        return (-_best_total_data_bytes(relay), fingerprint)
    if sort_mode == 'uptime':
        return (*_uptime_column_sort_key(relay), fingerprint)
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
        return (-_prioritized_flag_uptime_6m(relay), fingerprint)
    if sort_mode == 'ipv4':
        ip = _extract_ipv4(relay)
        return (0 if ip else 1, ip if ip else b'\xff' * 4, fingerprint)
    if sort_mode == 'flags':
        flags = relay.get('flags') or []
        role_rank = 0 if 'Exit' in flags else 1 if 'Guard' in flags else 2
        return (role_rank, '|'.join(sorted(flags)), fingerprint)
    if sort_mode == 'dns':
        rank = DNS_SORT_RANK.get(relay.get('exit_dns_health_status'), 3)
        return (rank, _safe_lower(relay.get('nickname')), fingerprint)
    if sort_mode == 'family':
        family_type = relay.get('family_support_type', 'none')
        family_len = len(relay.get('effective_family') or [])
        return (FAMILY_SORT_RANK.get(family_type, 4), -family_len, fingerprint)
    if sort_mode == 'country':
        return (_safe_lower(relay.get('country')), _safe_lower(relay.get('country_name')), fingerprint)
    if sort_mode == 'as_number':
        return (*_as_number_sort_value(relay), fingerprint)
    if sort_mode == 'as_name':
        as_name = relay.get('as_name') or ''
        return (0 if as_name else 1, _safe_lower(as_name), fingerprint)
    if sort_mode == 'platform':
        return (_safe_lower(relay.get('platform')), fingerprint)
    if sort_mode == 'first_seen':
        epoch = _parse_epoch(relay.get('first_seen'))
        return (-(epoch if epoch is not None else -1), fingerprint)
    if sort_mode == 'last_restarted':
        epoch = _parse_epoch(relay.get('last_restarted'))
        return (-(epoch if epoch is not None else -1), 0 if epoch is not None else 1, fingerprint)
    if sort_mode == 'ipv6':
        ip6 = _extract_ipv6(relay)
        return (0 if ip6 else 1, ip6 if ip6 else b'\xff' * 16, fingerprint)

    return (-int(relay.get('observed_bandwidth', 0) or 0), fingerprint)


def _sort_contact_relays(relays, sort_mode):
    """Sort plain relay dictionaries for contact single-table mode."""
    if not relays:
        return relays
    return sorted(relays, key=lambda relay: _relay_sort_key(relay, sort_mode))


def _sort_contact_section_entries(entries, sort_mode):
    """Sort wrapper dicts used by AROI sectioned contact tables."""
    if not entries:
        return entries
    return sorted(entries, key=lambda entry: _relay_sort_key(entry.get('relay', {}), sort_mode))


def _relay_has_ipv6(relay):
    """Determine whether a relay should be treated as IPv6-capable."""
    ipv6_support = relay.get('ipv6_support')
    if ipv6_support in ('both', 'ipv6_only'):
        return True
    for addr in relay.get('or_addresses') or []:
        _, ip_version = _safe_parse_ip_address(addr)
        if ip_version == 6:
            return True
    return False


def _contact_has_ipv6(base_template_args):
    """Determine if any rendered relay in contact context has IPv6."""
    relay_subset = base_template_args.get('relay_subset') or []
    if any(_relay_has_ipv6(relay) for relay in relay_subset):
        return True

    contact_validation_status = base_template_args.get('contact_validation_status')
    if isinstance(contact_validation_status, dict):
        for section_key in CONTACT_SECTION_KEYS:
            for entry in contact_validation_status.get(section_key, []):
                if _relay_has_ipv6(entry.get('relay', {})):
                    return True
    return False


def _build_contact_variant_args(base_template_args, sort_mode, contact_sort_enabled=True, enabled_modes=None):
    """Build per-variant template args from a shared contact-page base args dict."""
    variant_args = dict(base_template_args)
    variant_args['relay_subset'] = _sort_contact_relays(base_template_args.get('relay_subset', []), sort_mode)
    variant_args['contact_sort_mode'] = sort_mode
    variant_args['contact_sort_enabled'] = bool(contact_sort_enabled)
    variant_args['contact_sort_links'] = _contact_sort_links(enabled_modes if contact_sort_enabled else (sort_mode,))
    variant_args['sortable_scope'] = 'contact'

    contact_validation_status = base_template_args.get('contact_validation_status')
    if isinstance(contact_validation_status, dict):
        status_copy = dict(contact_validation_status)
        for section_key in CONTACT_SECTION_KEYS:
            status_copy[section_key] = _sort_contact_section_entries(
                contact_validation_status.get(section_key, []), sort_mode
            )
        variant_args['contact_validation_status'] = status_copy

    return variant_args
