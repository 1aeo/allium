#!/usr/bin/env python3
"""Simple optimization testing that focuses on template rendering performance."""

import time
import sys
import shutil
import os

# Add current directory to path for imports
sys.path.insert(0, '.')

def test_template_rendering_performance():
    """Test current template rendering performance"""
    try:
        from allium.lib.relays import Relays
        import tempfile
        
        temp_dir = tempfile.mkdtemp(prefix="perf_test_")
        
        print("📊 Testing current template rendering performance...")
        
        # Initialize relay set
        relay_set = Relays(temp_dir, "https://onionoo.torproject.org/details", progress=False)
        relay_set._fetch_onionoo_details()
        relay_set._preprocess_template_data()
        relay_set._categorize()
        
        # Get a small sample of family pages for testing
        family_keys = list(relay_set.json["sorted"]["family"].keys())[:50]  # Test with 50 pages
        family_data = {k: relay_set.json["sorted"]["family"][k] for k in family_keys}
        relay_set.json["sorted"]["family"] = family_data
        
        print(f"🎯 Testing with {len(family_keys)} family pages...")
        
        # Measure family page generation
        start_time = time.time()
        relay_set.write_pages_by_key("family")  
        family_time = time.time() - start_time
        
        print(f"✅ Current performance: {family_time:.2f}s for {len(family_keys)} pages")
        print(f"⚡ Average per page: {family_time/len(family_keys)*1000:.1f}ms")
        
        # Cleanup
        shutil.rmtree(temp_dir)
        
        return {
            'family_time': family_time,
            'family_pages': len(family_keys),
            'avg_per_page': family_time/len(family_keys)
        }
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return None

def apply_optimization_2():
    """Apply optimization #2: Pre-compute HTML elements"""
    print("🔧 Applying Optimization #2: HTML Pre-computation")
    
    # Backup
    shutil.copy('allium/lib/relays.py', 'allium/lib/relays.py.backup')
    
    try:
        with open('allium/lib/relays.py', 'r') as f:
            content = f.read()
        
        # Find the right place to add the optimization
        # Look for the end of existing preprocessing
        target = 'print(f"✅ Enhanced template preprocessing completed for {len(self.json[\'relays\'])} relays")'
        
        if target in content:
            # Add HTML pre-computation before the print statement
            addition = '''
            # OPTIMIZATION #2: Pre-compute HTML elements to avoid expensive Jinja2 operations
            from markupsafe import escape
            
            for relay in self.json["relays"]:
                if not relay.get('precomputed_html'):
                    relay['precomputed_html'] = {}
                
                # Pre-compute nickname cell with family link
                if relay.get('fingerprint') and relay.get('nickname'):
                    nickname_trunc = relay.get('nickname_truncated', relay['nickname'][:20] + ('...' if len(relay['nickname']) > 20 else ''))
                    relay_link = f'<a href="../../relay/{escape(relay["fingerprint"])}/">{nickname_trunc}</a>'
                    
                    if relay.get('effective_family') and len(relay['effective_family']) > 1:
                        family_link = f' (<a href="../../family/{escape(relay["fingerprint"])}/">{len(relay["effective_family"])}</a>)'
                        relay['precomputed_html']['nickname_cell'] = relay_link + family_link
                    else:
                        relay['precomputed_html']['nickname_cell'] = relay_link
                
                # Pre-compute contact cell
                if relay.get('contact') and relay.get('contact_md5'):
                    contact_esc = relay.get('contact_escaped', str(escape(relay['contact'])))
                    relay['precomputed_html']['contact_cell'] = f'<a href="../../contact/{relay["contact_md5"]}/" title="{contact_esc}" class="contact-text">{contact_esc}</a>'
                else:
                    relay['precomputed_html']['contact_cell'] = '<span title="none">none</span>'
                
                # Pre-compute AROI cell
                if relay.get('aroi_domain') and relay['aroi_domain'] not in ['none', '']:
                    aroi_esc = relay.get('aroi_domain_escaped', str(escape(relay['aroi_domain'])))
                    relay['precomputed_html']['aroi_cell'] = f'<a href="../../contact/{relay.get("contact_md5", "")}/" title="{aroi_esc}">{aroi_esc}</a>'
                else:
                    relay['precomputed_html']['aroi_cell'] = 'none'
            
'''
            new_content = content.replace(target, addition + '\n        ' + target)
            
            with open('allium/lib/relays.py', 'w') as f:
                f.write(new_content)
            
            print("✅ Applied optimization #2")
            return True
        else:
            print("❌ Could not find insertion point for optimization #2")
            return False
            
    except Exception as e:
        print(f"❌ Failed to apply optimization #2: {e}")
        return False

def restore_backup():
    """Restore backup file"""
    if os.path.exists('allium/lib/relays.py.backup'):
        shutil.copy('allium/lib/relays.py.backup', 'allium/lib/relays.py')
        os.remove('allium/lib/relays.py.backup')

def run_simple_tests():
    """Run simple optimization tests"""
    print("🚀 SIMPLE OPTIMIZATION TESTING")
    print("="*40)
    
    # Test baseline
    print("📊 BASELINE MEASUREMENT")
    baseline = test_template_rendering_performance()
    
    if not baseline:
        print("❌ Baseline test failed")
        return
    
    print(f"✅ Baseline: {baseline['family_time']:.2f}s for {baseline['family_pages']} pages")
    
    # Test optimization #2
    print("\n🧪 TESTING OPTIMIZATION #2")
    if apply_optimization_2():
        # Clear module cache to force reload
        if 'allium.lib.relays' in sys.modules:
            del sys.modules['allium.lib.relays']
        
        opt2_result = test_template_rendering_performance()
        
        if opt2_result:
            improvement = (baseline['family_time'] - opt2_result['family_time']) / baseline['family_time'] * 100
            print(f"📊 Optimization #2 result: {opt2_result['family_time']:.2f}s")
            print(f"📈 Improvement: {improvement:.1f}%")
            
            if improvement > 5:
                print("✅ OPTIMIZATION #2 IS BENEFICIAL")
            else:
                print("❌ OPTIMIZATION #2 IS NOT BENEFICIAL")
        else:
            print("❌ Optimization #2 test failed")
    
    # Restore original
    restore_backup()
    
    # Check optimization #4 (shared environment)
    print("\n🔍 CHECKING OPTIMIZATION #4")
    with open('allium/lib/relays.py', 'r') as f:
        content = f.read()
    
    if 'ENV = Environment(' in content:
        print("✅ Optimization #4: Shared Environment already implemented")
    else:
        print("❌ Optimization #4: Shared Environment not found") 
        
    print("\n✅ Testing complete")

if __name__ == "__main__":
    run_simple_tests() 