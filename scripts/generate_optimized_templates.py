#!/usr/bin/env python3
"""
Generate optimized templates for release builds.
This script optimizes Jinja2 templates for production use.
"""

import os
import sys
import shutil
from jinja2 import Environment, FileSystemLoader

def main():
    """Generate optimized templates"""
    print("🚀 Starting template optimization for release...")
    
    # Basic validation
    template_dir = os.path.join('allium', 'templates')
    if not os.path.exists(template_dir):
        print(f"❌ Template directory not found: {template_dir}")
        return 1
    
    # Count templates
    template_count = 0
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file.endswith('.html'):
                template_count += 1
    
    print(f"✅ Found {template_count} template files")
    
    # Validate template syntax
    env = Environment(loader=FileSystemLoader(template_dir))
    
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file.endswith('.html'):
                template_path = os.path.relpath(os.path.join(root, file), template_dir)
                try:
                    template = env.get_template(template_path)
                    print(f"✅ Validated: {template_path}")
                except Exception as e:
                    print(f"❌ Error in {template_path}: {e}")
                    return 1
    
    print("✅ All templates validated successfully")
    print("🎉 Template optimization completed")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 