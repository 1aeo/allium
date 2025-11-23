# Security Guide

This document outlines Allium's current security status, best practices, and guidelines for maintaining security throughout development.

---

## 🔒 Current Security Status

### Core Security Features
✅ **XSS Protection**: Jinja2 autoescape enabled globally  
✅ **Input Sanitization**: All external data sanitized  
✅ **HTML Escaping**: Centralized utilities for all output  
✅ **Static Generation**: No server-side vulnerabilities  
✅ **No JavaScript Dependencies**: Eliminates JS attack vectors  
✅ **Safe IP Parsing**: Validated against Python's ipaddress module  

### Recent Security Improvements
✅ **HTML Injection Fixes** (2024): Comprehensive XSS protection added  
✅ **AROI Security Audit** (2024): Input validation enhanced  
✅ **Centralized Escaping** (2024): Eliminated duplication, improved consistency  

---

## 🎯 Active Security Priorities

### Priority 1: Input Validation
**Status**: ✅ Good, continuous improvement needed

**Current Measures**:
- Onionoo API data validated before processing
- IP addresses validated via Python's ipaddress module
- Contact information sanitized and escaped
- Fingerprints validated against expected format

**Ongoing Work**:
- Add more comprehensive data structure validation
- Implement stricter type checking
- Enhanced error handling for malformed data

### Priority 2: Output Sanitization
**Status**: ✅ Strong, well-implemented

**Current Measures**:
- Global Jinja2 autoescape enabled
- Centralized HTML escaping utilities
- All user-provided data escaped before rendering
- No raw HTML injection points

**Maintenance**:
- Regular audits of template escaping
- Review new templates for escape requirements
- Monitor for escape bypasses

### Priority 3: Dependency Security
**Status**: ✅ Minimal dependencies = reduced attack surface

**Current Approach**:
- Production: Only Jinja2 required
- Development: Security scanning tools included
- Regular dependency updates
- Minimal external dependencies by design

---

## 🛡️ Security Testing

### Running Security Tests

```bash
# Security scanning with bandit
bandit -r allium/ -f json -o security-report.json

# Dependency vulnerability check
safety check -r config/requirements.txt

# Template linting
djlint allium/templates/ --check

# Full security test suite
pytest tests/ -m security
```

### Security Checklist
- [ ] All user input sanitized
- [ ] All output properly escaped
- [ ] No SQL injection points (static site)
- [ ] No XSS vulnerabilities
- [ ] No path traversal risks
- [ ] Dependencies up to date
- [ ] Security tests passing

---

## 🔍 Security Threat Model

### Attack Vectors (Static Site)

#### ✅ MITIGATED:
- **XSS Attacks**: Global autoescape + centralized escaping
- **HTML Injection**: All output sanitized
- **Path Traversal**: Output directory validation
- **SQL Injection**: N/A (no database)
- **CSRF**: N/A (no forms, no server-side state)
- **Session Hijacking**: N/A (no sessions)

#### ⚠️ MONITOR:
- **Malicious Data in Onionoo**: Input validation on API data
- **Large Data DoS**: Memory limits and timeout handling
- **Template Injection**: Jinja2 sandboxing, no user templates

#### 📋 FUTURE CONSIDERATIONS:
- **Supply Chain**: Dependency scanning and updates
- **CI/CD Security**: Secure build pipeline
- **Distribution**: Integrity verification (checksums)

---

## 🔐 Security Best Practices

### For Developers

#### ✅ DO:
```python
# Always escape user-provided data
from lib.html_escape_utils import safe_html_escape
escaped = safe_html_escape(user_input)

# Validate IP addresses
from lib.aroileaders import _safe_parse_ip_address
ip, version = _safe_parse_ip_address(address_string)
if not ip:
    raise ValidationError("Invalid IP address")

# Use centralized escaping utilities
from lib.html_escape_utils import create_bulk_escaper
escaper = create_bulk_escaper()
escaper.escape_all_relay_fields(relay)

# Validate output paths
from pathlib import Path
output_path = Path(user_path).resolve()
if not output_path.is_relative_to(allowed_root):
    raise SecurityError("Path not in allowed location")
```

#### ❌ DON'T:
```python
# Don't trust external data
relay_name = onionoo_data['nickname']  # Might contain HTML/JS
display_name = relay_name  # UNSAFE - needs escaping

# Don't disable autoescape
{{ relay.nickname | safe }}  # UNSAFE unless already escaped

# Don't build paths from user input
output_file = f"/var/www/{user_input}.html"  # Path traversal risk

# Don't bypass validation
if not validate_fingerprint(fp):
    # Don't just log and continue - handle error
    pass  # UNSAFE
```

### For Template Authors

#### ✅ DO:
```jinja2
{# Use pre-escaped data #}
{{ relay.nickname_escaped }}

{# Autoescape is enabled by default #}
{{ relay.contact }}  {# Automatically escaped #}

{# Use filters for formatting #}
{{ relay.bandwidth | format_bandwidth }}
```

#### ❌ DON'T:
```jinja2
{# Don't disable escaping without good reason #}
{{ relay.nickname | safe }}  {# UNSAFE #}

{# Don't use raw HTML from data #}
{{ relay.custom_html }}  {# UNSAFE #}

{# Don't bypass autoescape #}
{% autoescape false %}  {# NEVER DO THIS #}
```

---

## 🚨 Security Incident Response

### If You Find a Vulnerability

1. **DO NOT** create a public issue
2. **Report privately** to security contact
3. **Provide details**: 
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Process
1. **Acknowledge** receipt within 24 hours
2. **Assess** severity and impact
3. **Develop** fix and test thoroughly
4. **Release** patched version
5. **Disclose** responsibly after fix deployed

---

## 📚 Security Resources

### Internal Documentation
- [HTML Escaping Utilities](../architecture/README.md) - Implementation details
- [Input Validation](../architecture/data-pipeline.md) - Validation approach
- [Template Security](../architecture/template-optimization.md) - Safe templates

### Historical Security Reports
See [archive/security-details/](../archive/security-details/) for:
- **AROI Security Audit Report**: Comprehensive security review
- **HTML Injection Audit**: XSS vulnerability assessment
- **HTML Injection Fixes**: Remediation implementation

### External Resources
- [OWASP Top 10](https://owasp.org/Top10/)
- [Jinja2 Security](https://jinja.palletsprojects.com/en/3.1.x/templates/#autoescape-overrides)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)

---

## 🔧 Security Tools

### Included in Development Environment
```bash
# Install development dependencies
pip3 install -r config/requirements-dev.txt
```

**Tools**:
- **bandit**: Security issue scanner for Python
- **safety**: Dependency vulnerability checker
- **djlint**: HTML/template security linter
- **pytest**: Security-focused test suite

### CI/CD Integration
```yaml
# Example security checks in CI
- name: Security Scan
  run: |
    bandit -r allium/
    safety check
    djlint allium/templates/
```

---

## 📋 Security Audit Schedule

### Regular Reviews
- **Weekly**: Dependency updates check
- **Monthly**: Security scan with bandit
- **Quarterly**: Template security audit
- **Annually**: Comprehensive security review

### Next Scheduled Audit
**Date**: Q1 2025  
**Scope**: Full security assessment  
**Focus**: Input validation, output sanitization, dependency security

---

## 🎯 Contributing Securely

### Pull Request Security Checklist
- [ ] No new XSS vulnerabilities introduced
- [ ] All user input validated
- [ ] All output properly escaped
- [ ] No sensitive data in commits
- [ ] Security tests added for new features
- [ ] Bandit scan passes
- [ ] Template security verified

### Code Review Focus
- Input validation on external data
- Output escaping in templates
- Path handling for file operations
- Error handling for security failures
- No hardcoded secrets or credentials

---

**Last Updated**: 2025-11-23  
**Security Contact**: See SECURITY.md (if exists) or repository maintainers  
**Current Status**: Strong security posture, continuous monitoring  
**Next Audit**: Q1 2025
