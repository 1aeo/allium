#!/usr/bin/env python3
"""
Script to fix HTML injection vulnerabilities in Jinja2 templates by adding |escape filters
where needed based on the audit findings.
"""

import os
import re
import sys
from pathlib import Path

def fix_or_addresses(content):
    """Fix unescaped OR addresses in relay-info.html"""
    # Pattern to find unescaped or_addresses loops
    pattern = r"(\{\%\s*for\s+address\s+in\s+relay\['or_addresses'\]\s*-?\%\})(\{\{\s*address\s*\}\})"
    replacement = r"\1{{ address|escape }}"
    
    return re.sub(pattern, replacement, content)

def fix_breadcrumb_data(content):
    """Fix unescaped breadcrumb data in macros.html"""
    # Patterns for different breadcrumb data fields
    patterns = [
        (r"(\{\{\s*page_data\.as_number\s*\}\})", r"{{ page_data.as_number|escape }}"),
        (r"(\{\{\s*page_data\.country_name\s*\}\})", r"{{ page_data.country_name|escape }}"),
        (r"(\{\{\s*page_data\.platform_name\s*\}\})", r"{{ page_data.platform_name|escape }}"),
        (r"(\{\{\s*page_data\.nickname\s*\}\})", r"{{ page_data.nickname|escape }}"),
        (r"(\{\{\s*page_data\.aroi_domain\s*\}\})", r"{{ page_data.aroi_domain|escape }}"),
        (r"(\{\{\s*page_data\.contact_hash\[:8\]\s*\}\})", r"{{ page_data.contact_hash[:8]|escape }}"),
        (r"(\{\{\s*page_data\.family_hash\[:8\]\s*\}\})", r"{{ page_data.family_hash[:8]|escape }}"),
        (r"(\{\{\s*page_data\.date\s*\}\})", r"{{ page_data.date|escape }}"),
        (r"(\{\{\s*page_data\.flag_name\|title\s*\}\})", r"{{ page_data.flag_name|title|escape }}"),
    ]
    
    for pattern, replacement in patterns:
        # Only replace if not already escaped
        if not re.search(pattern.replace(r"\}\}", r"\|escape\s*\}\}"), content):
            content = re.sub(pattern, replacement, content)
    
    return content

def enable_autoescape_in_relays_py():
    """Enable autoescape in Jinja2 configuration in relays.py"""
    relays_path = Path("allium/lib/relays.py")
    if not relays_path.exists():
        print(f"Warning: {relays_path} not found")
        return
    
    content = relays_path.read_text()
    
    # Pattern to find the Environment initialization
    pattern = r"(ENV\s*=\s*Environment\(\s*[^)]+)(trim_blocks=True,\s*lstrip_blocks=True,)"
    replacement = r"\1\2\n    autoescape=True,"
    
    # Check if autoescape is already present
    if "autoescape=True" not in content:
        content = re.sub(pattern, replacement, content)
        relays_path.write_text(content)
        print(f"✅ Added autoescape=True to Jinja2 Environment in {relays_path}")
    else:
        print(f"ℹ️  autoescape=True already present in {relays_path}")

def fix_template_file(file_path):
    """Fix vulnerabilities in a single template file"""
    content = file_path.read_text()
    original_content = content
    
    if file_path.name == "relay-info.html":
        content = fix_or_addresses(content)
    
    if file_path.name == "macros.html":
        content = fix_breadcrumb_data(content)
    
    if content != original_content:
        file_path.write_text(content)
        print(f"✅ Fixed vulnerabilities in {file_path}")
        return True
    return False

def main():
    """Main function to fix all identified vulnerabilities"""
    print("🔧 Starting HTML injection vulnerability fixes...\n")
    
    # Fix autoescape in relays.py
    enable_autoescape_in_relays_py()
    
    # Fix templates
    templates_dir = Path("allium/templates")
    if not templates_dir.exists():
        print(f"Error: Templates directory {templates_dir} not found")
        sys.exit(1)
    
    fixed_count = 0
    for template_file in templates_dir.glob("*.html"):
        if fix_template_file(template_file):
            fixed_count += 1
    
    print(f"\n✨ Fixed {fixed_count} template files")
    print("\n📋 Summary of fixes applied:")
    print("  - Added |escape filter to OR addresses in relay-info.html")
    print("  - Added |escape filter to breadcrumb data in macros.html")
    print("  - Enabled autoescape in Jinja2 configuration")
    print("\n⚠️  Note: Title blocks and numeric values were not modified as they pose minimal risk")
    print("\n✅ HTML injection vulnerability fixes completed!")

if __name__ == "__main__":
    main()