#!/usr/bin/env python3
"""Optimization tester for Allium template rendering performance."""

import subprocess
import time
import os
import sys
import tempfile
import shutil
import json
import re

def run_allium_benchmark():
    """Run allium and extract timing information"""
    temp_dir = tempfile.mkdtemp(prefix="allium_test_")
    
    try:
        start_time = time.time()
        result = subprocess.run([
            sys.executable, 'allium/allium.py', 
            '--out', temp_dir, 
            '--progress'
        ], capture_output=True, text=True, timeout=300)
        
        total_time = time.time() - start_time
        
        if result.returncode != 0:
            print("❌ Execution failed")
            return None
        
        # Extract family page timing from output
        lines = result.stdout.split('\n')
        family_time = None
        family_pages = None
        
        for line in lines:
            if 'Generated' in line and 'family pages' in line and 'in' in line:
                parts = line.split()
                try:
                    for i, part in enumerate(parts):
                        if part == 'Generated':
                            family_pages = int(parts[i+1])
                        elif part == 'in' and i+1 < len(parts):
                            time_str = parts[i+1].rstrip('s')
                            family_time = float(time_str)
                            break
                except (ValueError, IndexError):
                    continue
        
        return {
            'total_time': total_time,
            'family_time': family_time,
            'family_pages': family_pages
        }
        
    except subprocess.TimeoutExpired:
        print("⏰ Execution timed out")
        return None
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def test_optimization_2():
    """Test bulk context optimization"""
    print("🧪 Testing Optimization #2: Bulk Context Optimization")
    
    # Backup
    shutil.copy('allium/lib/relays.py', 'allium/lib/relays.py.backup')
    
    try:
        # Read current file
        with open('allium/lib/relays.py', 'r') as f:
            content = f.read()
        
        # Add HTML pre-computation to _preprocess_template_data
        addition = '''
            # OPTIMIZATION #2: Pre-compute HTML elements
            relay['precomputed_html'] = {}
            
            # Pre-compute nickname cell with family link
            if relay.get('fingerprint') and relay.get('nickname'):
                relay_link = f'<a href="../../relay/{escape(relay["fingerprint"])}/">{relay["nickname_truncated"]}</a>'
                if relay.get('effective_family') and len(relay['effective_family']) > 1:
                    family_link = f' (<a href="../../family/{escape(relay["fingerprint"])}/">{len(relay["effective_family"])}</a>)'
                    relay['precomputed_html']['nickname_cell'] = relay_link + family_link
                else:
                    relay['precomputed_html']['nickname_cell'] = relay_link
            
            # Pre-compute contact cell
            if relay.get('contact') and relay.get('contact_md5'):
                relay['precomputed_html']['contact_cell'] = f'<a href="../../contact/{relay["contact_md5"]}/" title="{relay["contact_escaped"]}" class="contact-text">{relay["contact_escaped"]}</a>'
            else:
                relay['precomputed_html']['contact_cell'] = '<span title="none">none</span>'
'''
        
        # Find insertion point in _preprocess_template_data
        insertion_point = 'print(f"✅ Enhanced template preprocessing completed for {len(self.json[\'relays\'])} relays")'
        if insertion_point in content:
            new_content = content.replace(insertion_point, addition + '\n        ' + insertion_point)
            
            with open('allium/lib/relays.py', 'w') as f:
                f.write(new_content)
            
            print("✅ Applied optimization #2")
            return run_allium_benchmark()
        else:
            print("❌ Could not apply optimization #2")
            return None
            
    finally:
        # Restore
        shutil.copy('allium/lib/relays.py.backup', 'allium/lib/relays.py')
        os.remove('allium/lib/relays.py.backup')

def test_optimization_3():
    """Test template simplification"""
    print("🧪 Testing Optimization #3: Template Simplification")
    
    # Backup
    shutil.copy('allium/templates/relay-list.html', 'allium/templates/relay-list.html.backup')
    
    try:
        # Read current template
        with open('allium/templates/relay-list.html', 'r') as f:
            template = f.read()
        
        # Replace complex nickname cell with pre-computed version
        old_nickname = '''<td title="{{ relay['nickname']|escape }}">
		<a href="../../relay/{{ relay['fingerprint']|escape }}/">{{ relay['nickname']|truncate(20) }}</a>
		{% if relay['effective_family'] is defined and relay['effective_family']|length > 1 -%}
		 (<a href="../../family/{{ relay['fingerprint']|escape }}/">{{ relay['effective_family']|length }}</a>)
		{% endif -%}
	    </td>'''
        
        new_nickname = '''<td title="{{ relay['nickname']|escape }}">
		{{ relay['precomputed_html']['nickname_cell'] }}
	    </td>'''
        
        if old_nickname in template:
            new_template = template.replace(old_nickname, new_nickname)
            
            with open('allium/templates/relay-list.html', 'w') as f:
                f.write(new_template)
            
            print("✅ Applied optimization #3")
            
            # Also need to apply optimization #2 for this to work
            shutil.copy('allium/lib/relays.py', 'allium/lib/relays.py.backup2')
            test_optimization_2()  # Apply #2 without measuring
            
            result = run_allium_benchmark()
            
            # Restore relays.py
            shutil.copy('allium/lib/relays.py.backup2', 'allium/lib/relays.py')
            os.remove('allium/lib/relays.py.backup2')
            
            return result
        else:
            print("❌ Could not apply optimization #3")
            return None
            
    finally:
        # Restore
        shutil.copy('allium/templates/relay-list.html.backup', 'allium/templates/relay-list.html')
        os.remove('allium/templates/relay-list.html.backup')

def main():
    """Run optimization tests"""
    print("🚀 OPTIMIZATION TESTING FRAMEWORK")
    print("="*50)
    
    # Baseline
    print("📊 Measuring baseline performance...")
    baseline = run_allium_benchmark()
    
    if not baseline:
        print("❌ Baseline measurement failed")
        return
    
    print(f"✅ Baseline: {baseline['family_time']:.2f}s for {baseline['family_pages']} family pages")
    
    results = {'baseline': baseline}
    
    # Test optimization #2
    opt2 = test_optimization_2()
    if opt2:
        improvement2 = (baseline['family_time'] - opt2['family_time']) / baseline['family_time'] * 100
        print(f"📊 Optimization #2: {opt2['family_time']:.2f}s ({improvement2:.1f}% {'improvement' if improvement2 > 0 else 'slower'})")
        results['optimization_2'] = {'result': opt2, 'improvement': improvement2}
    
    # Test optimization #3  
    opt3 = test_optimization_3()
    if opt3:
        improvement3 = (baseline['family_time'] - opt3['family_time']) / baseline['family_time'] * 100
        print(f"📊 Optimization #3: {opt3['family_time']:.2f}s ({improvement3:.1f}% {'improvement' if improvement3 > 0 else 'slower'})")
        results['optimization_3'] = {'result': opt3, 'improvement': improvement3}
    
    # Check optimization #4 (shared environment)
    with open('allium/lib/relays.py', 'r') as f:
        content = f.read()
    
    if 'ENV = Environment(' in content:
        print("✅ Optimization #4: Shared Environment already implemented")
        results['optimization_4'] = {'already_implemented': True}
    else:
        print("❌ Optimization #4: Shared Environment not found")
        results['optimization_4'] = {'not_implemented': True}
    
    # Summary
    print("\n" + "="*50)
    print("📋 SUMMARY")
    print("="*50)
    
    beneficial = []
    
    for opt in ['optimization_2', 'optimization_3']:
        if opt in results and 'improvement' in results[opt]:
            imp = results[opt]['improvement']
            if imp > 5:
                print(f"✅ {opt}: {imp:.1f}% improvement - BENEFICIAL")
                beneficial.append(opt)
            else:
                print(f"❌ {opt}: {imp:.1f}% - NOT BENEFICIAL")
    
    if results.get('optimization_4', {}).get('already_implemented'):
        print("✅ optimization_4: Already implemented - BENEFICIAL")
        beneficial.append('optimization_4')
    
    print(f"\n🎯 {len(beneficial)}/3 optimizations are beneficial")
    
    # Save results
    with open('optimization_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("📁 Results saved to optimization_results.json")

if __name__ == "__main__":
    main() 