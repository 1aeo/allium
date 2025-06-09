#!/usr/bin/env python3
"""
Check for potentially unescaped variables in Jinja2 templates.
This script helps identify XSS vulnerabilities in the aroi-leaderboard templates.
"""

import os
import re
from pathlib import Path

def check_template_file(filepath):
    """Check a single template file for potentially unescaped variables."""
    vulnerabilities = []
    
    with open(filepath, 'r') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Pattern to match Jinja2 variables without escape filter
    # Excludes variables that already have filters applied
    variable_pattern = re.compile(r'\{\{([^}]+)\}\}')
    
    for line_num, line in enumerate(lines, 1):
        matches = variable_pattern.findall(line)
        
        for match in matches:
            # Skip if it already has escape filter
            if '|escape' in match:
                continue
            
            # Skip if it's a function call or has other filters
            if '(' in match or '|' in match:
                # Check if the filter is safe (not just any filter)
                safe_filters = ['escape', 'e', 'tojson', 'int', 'float', 'length', 'count']
                has_safe_filter = any(f'|{filter}' in match for filter in safe_filters)
                if has_safe_filter:
                    continue
            
            # Skip if it's a control structure or comparison
            if any(op in match for op in ['if ', 'for ', 'in ', '==', '!=', '<', '>', 'and ', 'or ', 'not ']):
                continue
            
            # This looks like an unescaped variable
            var_name = match.strip()
            vulnerabilities.append({
                'line': line_num,
                'variable': var_name,
                'context': line.strip()
            })
    
    return vulnerabilities

def main():
    """Check all template files in the aroi-leaderboard project."""
    template_dir = Path('allium/templates')
    
    if not template_dir.exists():
        print("Error: Template directory not found. Run this from the project root.")
        return
    
    print("Checking for potentially unescaped variables in templates...\n")
    
    total_vulnerabilities = 0
    files_with_issues = 0
    
    for template_file in sorted(template_dir.glob('*.html')):
        vulnerabilities = check_template_file(template_file)
        
        if vulnerabilities:
            files_with_issues += 1
            total_vulnerabilities += len(vulnerabilities)
            
            print(f"\n{'='*60}")
            print(f"File: {template_file}")
            print(f"Found {len(vulnerabilities)} potentially unescaped variable(s):")
            print('='*60)
            
            for vuln in vulnerabilities:
                print(f"\nLine {vuln['line']}: {vuln['variable']}")
                print(f"Context: {vuln['context']}")
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(f"Total files checked: {len(list(template_dir.glob('*.html')))}")
    print(f"Files with potential issues: {files_with_issues}")
    print(f"Total potential vulnerabilities: {total_vulnerabilities}")
    
    if total_vulnerabilities > 0:
        print("\n⚠️  WARNING: Found potentially unescaped variables!")
        print("These could lead to XSS vulnerabilities if they contain user-controlled data.")
        print("\nRecommended fixes:")
        print("1. Enable autoescape in Jinja2 Environment configuration")
        print("2. Add |escape filter to all user-controlled variables")
        print("3. Review each case to ensure proper escaping for the context")
    else:
        print("\n✅ No obvious unescaped variables found.")
        print("However, manual review is still recommended for:")
        print("- Variables with custom filters")
        print("- JavaScript contexts")
        print("- URL contexts")
        print("- Any use of |safe filter")

if __name__ == "__main__":
    main()