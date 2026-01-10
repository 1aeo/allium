# Security Guide

**Audience**: Contributors  
**Scope**: Security practices and guidelines

## Security Model

Allium is a static site generator with minimal attack surface:

| Threat | Mitigation |
|--------|------------|
| XSS | Jinja2 autoescape enabled globally |
| HTML Injection | Centralized escaping utilities |
| Path Traversal | Output directory validation |
| SQL Injection | N/A (no database) |
| CSRF | N/A (no forms/sessions) |
| Supply Chain | Minimal dependencies (only Jinja2) |

## Security Features

- **Global autoescape**: All Jinja2 output escaped by default
- **Centralized escaping**: `lib/html_escape_utils.py` for consistent sanitization
- **IP validation**: `ipaddress` module for safe parsing
- **Static output**: No server-side code execution

## Running Security Checks

```bash
# Security scanner
bandit -r allium/

# Dependency vulnerabilities
safety check -r config/requirements.txt

# Template linter
djlint allium/templates/ --check

# All checks
bandit -r allium/ && safety check && djlint allium/templates/
```

## Best Practices

### Python Code

```python
# DO: Use centralized escaping
from lib.html_escape_utils import safe_html_escape
escaped = safe_html_escape(user_input)

# DO: Validate IP addresses
from lib.aroileaders import _safe_parse_ip_address
ip, version = _safe_parse_ip_address(address_string)

# DON'T: Trust external data without escaping
display_name = onionoo_data['nickname']  # UNSAFE
```

### Templates

```jinja2
{# DO: Let autoescape handle it #}
{{ relay.contact }}

{# DO: Use pre-escaped fields #}
{{ relay.nickname_escaped }}

{# DON'T: Disable escaping #}
{{ relay.nickname | safe }}  {# UNSAFE #}

{# DON'T: Disable autoescape #}
{% autoescape false %}  {# NEVER #}
```

## Reporting Vulnerabilities

1. Do NOT create public issues for security vulnerabilities
2. Contact repository maintainers privately
3. Include: description, reproduction steps, impact, suggested fix

## PR Security Checklist

- [ ] No XSS vulnerabilities introduced
- [ ] All user input validated
- [ ] All output properly escaped
- [ ] No sensitive data in commits
- [ ] Bandit scan passes

## How to Verify

```bash
# Check security tools are installed
bandit --version
safety --version

# Run full security scan
bandit -r allium/ -f json -o /tmp/security-report.json
cat /tmp/security-report.json | python3 -m json.tool | head -20
```
