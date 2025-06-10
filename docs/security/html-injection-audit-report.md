# HTML Injection Vulnerability Audit Report

## Executive Summary

This report details the findings from a security audit of all Jinja2 templates in the Allium project, specifically focusing on HTML injection vulnerabilities through unescaped Onionoo API data.

## Audit Methodology

1. Examined all Jinja2 templates in `/allium/templates/`
2. Analyzed the data flow from Onionoo API through Python processing to template rendering
3. Identified all instances where variables are rendered without proper escaping
4. Assessed the risk level of each finding

## Key Findings

### ✅ Good Security Practices Found

1. **Pre-escaping in Python**: The `_preprocess_template_data()` method in `relays.py` pre-escapes several frequently used fields:
   - `contact_escaped` - Contact information is HTML-escaped
   - `flags_escaped` - Flag names are HTML-escaped
   - `flags_lower_escaped` - Lowercase flag names are HTML-escaped
   - `first_seen_date_escaped` - First seen dates are HTML-escaped

2. **Extensive use of |escape filter**: Most templates properly use the `|escape` filter for user-provided data like:
   - Nicknames
   - Contact information
   - AS names
   - Country names
   - Platform names
   - Fingerprints

### ⚠️ Potential Vulnerabilities Found

#### 1. **Unescaped OR Addresses** (Medium Risk)
**Location**: `relay-info.html` lines 172, 176, 178
```jinja
{% for address in relay['or_addresses'] -%}{{ address }}{% if not loop.last %}, {% endif %}{% endfor -%}
```
**Risk**: OR addresses from Onionoo API are rendered without escaping. While typically these are IP:port combinations, malformed data could lead to XSS.

#### 2. **Unescaped Breadcrumb Data** (Low-Medium Risk)
**Location**: `macros.html` breadcrumbs macro
```jinja
<li style="display: inline; color: #777;"> > {{ page_data.as_number }}</li>
<li style="display: inline; color: #777;"> > {{ page_data.country_name }}</li>
<li style="display: inline; color: #777;"> > {{ page_data.platform_name }}</li>
<li style="display: inline; color: #777;"> > {{ page_data.nickname }}</li>
```
**Risk**: Breadcrumb data is not escaped. While this data comes from internal page context, it originates from Onionoo API.

#### 3. **Mixed Escaping in Title Blocks** (Low Risk)
**Location**: Various templates in `{% block title %}` sections
```jinja
{% block title %}Tor Relays :: {{ platform_name }}{% endblock %}
{% block header %}View Platform {{ platform_name }} Details{% endblock %}
```
**Risk**: Title blocks don't escape variables. While browsers typically don't execute scripts in title tags, it's still a best practice to escape.

#### 4. **Numeric Values Without Escaping** (Very Low Risk)
**Location**: Throughout templates
- Bandwidth values: `{{ obs_bandwidth }}`, `{{ guard_bw }}`, etc.
- Counts: `{{ v['guard_count'] }}`, `{{ v['middle_count'] }}`, etc.
- Percentages: `{{ relays.json['network_totals']['measured_percentage'] }}`

**Risk**: These are numeric values processed by Python, so XSS risk is minimal, but escaping would be a defense-in-depth measure.

## Recommendations

### High Priority
1. **Escape OR addresses** in `relay-info.html`:
   ```jinja
   {% for address in relay['or_addresses'] -%}{{ address|escape }}{% if not loop.last %}, {% endif %}{% endfor -%}
   ```

2. **Escape breadcrumb data** in `macros.html`:
   ```jinja
   <li style="display: inline; color: #777;"> > {{ page_data.as_number|escape }}</li>
   <li style="display: inline; color: #777;"> > {{ page_data.country_name|escape }}</li>
   <li style="display: inline; color: #777;"> > {{ page_data.platform_name|escape }}</li>
   <li style="display: inline; color: #777;"> > {{ page_data.nickname|escape }}</li>
   ```

### Medium Priority
3. **Enable autoescape globally** in Jinja2 configuration:
   ```python
   ENV = Environment(
       loader=FileSystemLoader(os.path.join(ABS_PATH, "../templates")),
       trim_blocks=True,
       lstrip_blocks=True,
       autoescape=True  # Add this line
   )
   ```

### Low Priority
4. **Escape title blocks** for defense-in-depth
5. **Consider escaping numeric values** even though risk is minimal

## Conclusion

The Allium project demonstrates good security awareness with extensive use of the `|escape` filter and pre-escaping of commonly used fields. However, there are a few areas where data from the Onionoo API is rendered without proper escaping, particularly OR addresses and breadcrumb data. These should be addressed to ensure complete protection against HTML injection attacks.

The most critical finding is the unescaped OR addresses in `relay-info.html`, as this directly renders external data without sanitization.