# AROI-Leaderboard Security Audit Report: HTML Injection Vulnerabilities

> **UPDATE: All vulnerabilities identified in this report have been fixed. See SECURITY_FIXES_APPLIED.md for details on the remediation.**

## Executive Summary

This security audit has identified **multiple critical HTML injection (XSS) vulnerabilities** in the aroi-leaderboard codebase. These vulnerabilities arise from insufficient HTML escaping of user-controlled data received from the Onionoo API before rendering it in HTML templates.

**Severity: HIGH** - Remote attackers could potentially inject malicious JavaScript code through relay metadata fields.

## Key Findings

### 1. Data Flow Analysis

The application fetches relay data from the Onionoo API (`https://onionoo.torproject.org/details`) and processes it through the following flow:

1. **Data Fetch**: `allium/lib/relays.py` → `_fetch_onionoo_details()` fetches JSON data
2. **Data Processing**: Various processing methods parse and organize the data
3. **Template Rendering**: Jinja2 templates render the data into HTML pages

### 2. Critical Configuration Issue: Jinja2 Autoescape Disabled

**The Jinja2 template environment is configured WITHOUT autoescape enabled:**

```python
# allium/lib/relays.py, lines 19-23
ENV = Environment(
    loader=FileSystemLoader(os.path.join(ABS_PATH, "../templates")),
    trim_blocks=True,
    lstrip_blocks=True,
)
```

This means **ALL template variables must be manually escaped** using the `|escape` filter, or XSS vulnerabilities will occur.

### 3. Partial Security Measures Identified

The codebase does implement some security measures:

- **Pre-escaping in relays.py**: The `_preprocess_template_data()` method pre-escapes some fields:
  - `contact` → `contact_escaped`
  - `flags` → `flags_escaped` and `flags_lower_escaped`
  - `first_seen` → `first_seen_date_escaped`

- **Manual escaping in templates**: Many template variables use the `|escape` filter

### 4. Critical Vulnerabilities Found

Despite partial protections, numerous variables from the Onionoo API are rendered without proper escaping:

#### A. relay-info.html (Individual Relay Pages)
- **Line 4**: `{% block title -%} Tor Relays :: {{ relay['nickname'] }}` - Unescaped nickname in page title
- **Line 8**: `<h2>View Relay "{{ relay['nickname'] }}"</h2>` - Unescaped nickname in header
- **Lines 168-170**: OR addresses rendered without escaping:
  ```html
  {% for address in relay['or_addresses'] -%}{{ address }}{% if not loop.last %}, {% endif %}{% endfor -%}
  ```

#### B. as.html (AS Network Pages)
- **Line 5**: `{% block title %}Tor Relays :: {{ as_name }} ({{ as_number }}){% endblock %}` - While as_name is escaped when assigned, the output is not escaped
- **Line 6**: `{% block header %}View {{ as_number }} {{ as_name }} Details{% endblock %}`
- **Line 9**: `{% block description %}{{ as_number }} {{ as_name }} network summary:`

#### C. country.html (Country Pages)
- **Line 10**: `{% block title %}Tor Relays :: {{ country_name }}{% endblock %}` - Unescaped country name
- **Line 11**: `{% block header %}View {{ country_name }} Details{% endblock %}`
- **Line 15**: `{% block description %}{{ country_name }} ({{ country_abbr }}) summary:`

#### D. platform.html (Platform Pages)
- **Line 3**: `{% block title %}Tor Relays :: {{ platform_name }}{% endblock %}`
- **Line 4**: `{% block header %}View Platform {{ platform_name }} Details{% endblock %}`
- **Line 8**: `{% block description %}Platform {{ value }} summary:`

#### E. first_seen.html
- **Line 3**: `{% block title %}Tor Relays :: First Seen {{ first_seen_date }}{% endblock %}`
- **Line 4**: `{% block header %}View First Seen {{ first_seen_date }} Details{% endblock %}`
- **Line 8**: `{% block description %}Relays started on {{ value }} summary:`

#### F. macros.html (Breadcrumb Navigation)
Multiple unescaped outputs in breadcrumb navigation:
- **Line 6**: `{{ page_data.as_number }}`
- **Line 9**: `{{ page_data.aroi_domain }}` and `{{ page_data.contact_hash[:8] }}`
- **Line 12**: `{{ page_data.country_name }}`
- **Line 15**: `{{ page_data.aroi_domain }}` and `{{ page_data.family_hash[:8] }}`
- **Line 18**: `{{ page_data.platform_name }}`
- **Line 21**: `{{ page_data.date }}`
- **Line 24**: `{{ page_data.flag_name|title }}`
- **Line 30**: `{{ page_data.nickname }}`

#### G. Smart Context Variables (index.html and misc-*.html)
Multiple smart context variables rendered without escaping:
- Critical AS list in misc-networks.html: `{{ relays.json.smart_context.infrastructure_dependency.template_optimized.critical_as_list|join(', ') }}`
- Various tooltip text containing unescaped data

### 5. Attack Vectors

An attacker controlling a Tor relay could inject malicious HTML/JavaScript through various fields:

1. **Relay Nickname**: Most critical - appears unescaped in titles and headers
2. **AS Name**: Could inject through AS name fields  
3. **OR Addresses**: IP addresses rendered without escaping
4. **Platform Information**: Platform names rendered unsafely
5. **Contact Information**: While partially protected, some instances may be vulnerable
6. **Country Names**: Though less likely, custom country names could be injected
7. **Smart Context Data**: Aggregated data that includes relay information

### 6. Impact Assessment

- **Stored XSS**: Malicious scripts would be stored in the generated static HTML files
- **Persistence**: Attacks persist until the next site regeneration
- **Wide Distribution**: Malicious content served to all visitors of affected pages
- **Trust Exploitation**: Attacks appear to come from the trusted relay metrics site

## Recommendations

### Immediate Actions Required

1. **Enable Auto-escaping in Jinja2** (CRITICAL):
   ```python
   # In allium/lib/relays.py
   ENV = Environment(
       loader=FileSystemLoader(os.path.join(ABS_PATH, "../templates")),
       trim_blocks=True,
       lstrip_blocks=True,
       autoescape=True
   )
   ```

2. **Audit All Templates**: Even with autoescape enabled, review all templates to ensure:
   - No use of `|safe` filter on untrusted data
   - No use of `{% autoescape false %}` blocks with untrusted data
   - Proper escaping for non-HTML contexts (JavaScript, URLs, etc.)

3. **Critical Variables to Fix Immediately**:
   - `relay['nickname']` - All occurrences
   - `relay['or_addresses']` - All elements
   - `as_name`, `country_name`, `platform_name` - In all contexts
   - All breadcrumb navigation variables
   - Smart context aggregated data

### Example Fixes

```html
<!-- VULNERABLE -->
{% block title %}Tor Relays :: {{ relay['nickname'] }}{% endblock %}

<!-- SECURE (with manual escaping) -->
{% block title %}Tor Relays :: {{ relay['nickname']|escape }}{% endblock %}

<!-- SECURE (with autoescape enabled globally) -->
{% block title %}Tor Relays :: {{ relay['nickname'] }}{% endblock %}
```

### Additional Security Measures

1. **Content Security Policy**: Add CSP headers to static files to mitigate XSS impact
2. **Input Validation**: Validate relay data format before processing
3. **Regular Security Audits**: Implement automated checks for unescaped outputs
4. **Template Security Linting**: Use tools like `jinjalint` to detect missing escape filters
5. **Consider using MarkupSafe**: Jinja2's companion library for automatic string escaping

## Conclusion

The aroi-leaderboard application has significant HTML injection vulnerabilities due to:
1. **Jinja2 autoescape being disabled** - requiring manual escaping of every variable
2. **Inconsistent manual escaping** - many variables are rendered without the `|escape` filter
3. **Incomplete pre-escaping** - only some fields are pre-escaped in Python code

**Immediate remediation is required** to protect users from potential attacks through maliciously crafted relay metadata. The simplest and most effective fix is to enable autoescape in the Jinja2 environment configuration.

All data from external sources (Onionoo API) must be treated as untrusted and properly escaped before rendering in HTML context.