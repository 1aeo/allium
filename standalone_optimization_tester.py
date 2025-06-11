#!/usr/bin/env python3
"""
Standalone optimization tester that measures before/after performance
using subprocess execution to avoid import issues.
"""

import subprocess
import time
import os
import sys
import tempfile
import shutil
import json
import re

def measure_performance_via_subprocess(test_name="baseline", modifications=None):
    """Measure performance using subprocess execution"""
    print(f"📊 Measuring {test_name} performance...")
    
    # Create temporary output directory
    temp_dir = tempfile.mkdtemp(prefix=f"{test_name}_test_")
    print(f"📁 Using temporary directory: {temp_dir}")
    
    try:
        # Run allium with limited family pages for testing
        start_time = time.time()
        
        result = subprocess.run([
            sys.executable, 'allium/allium.py', 
            '--out', temp_dir, 
            '--progress'
        ], capture_output=True, text=True, timeout=300)
        
        execution_time = time.time() - start_time
        
        if result.returncode != 0:
            print(f"❌ {test_name} execution failed:")
            print("STDOUT:", result.stdout[-500:] if result.stdout else "None")
            print("STDERR:", result.stderr[-500:] if result.stderr else "None")
            return None
        
        # Parse the output to extract family page timing
        family_time = None
        family_pages = None
        
        for line in result.stdout.split('\n'):
            if 'family page generation complete' in line and 'Generated' in line:
                # Next line should have timing info
                continue
            elif line.strip().startswith('📊 Generated') and 'pages in' in line and 'family' in result.stdout:
                parts = line.split()
                try:
                    family_pages = int(parts[2])
                    time_str = parts[5].rstrip('s')
                    family_time = float(time_str)
                    break
                except (IndexError, ValueError):
                    continue
        
        print(f"✅ {test_name} execution completed in {execution_time:.2f}s")
        if family_time and family_pages:
            print(f"🎯 Family pages: {family_pages} in {family_time:.2f}s ({family_time/family_pages*1000:.1f}ms per page)")
        
        return {
            'total_time': execution_time,
            'family_time': family_time,
            'family_pages': family_pages,
            'stdout': result.stdout,
            'test_name': test_name
        }
        
    except subprocess.TimeoutExpired:
        print(f"⏰ {test_name} execution timed out after 300 seconds")
        return None
    except Exception as e:
        print(f"❌ {test_name} execution failed: {e}")
        return None
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def apply_optimization_2():
    """Apply optimization #2: Bulk Template Context Optimization"""
    print("🔧 Applying Optimization #2: Bulk Template Context Optimization")
    
    # Backup original file
    shutil.copy('allium/lib/relays.py', 'allium/lib/relays.py.opt2_backup')
    
    # Enhanced _preprocess_template_data method
    enhanced_method = '''    def _preprocess_template_data(self):
        """
        Pre-process template data to avoid expensive Jinja2 operations.
        Enhanced with bulk context optimization for HTML link pre-computation.
        """
        if not self.json.get("relays"):
            return
            
        print("🎨 Pre-processing template data with bulk context optimization...")
        
        from markupsafe import escape
        
        for relay in self.json["relays"]:
            # Existing bandwidth formatting
            if relay.get('observed_bandwidth'):
                unit = self._determine_unit(relay['observed_bandwidth'])
                relay['obs_bandwidth_with_unit'] = self._format_bandwidth_with_unit(relay['observed_bandwidth'], unit)
            
            # Existing time formatting
            if relay.get('last_restarted'):
                relay['last_restarted_ago'] = self._format_time_ago(relay['last_restarted'])
            
            if relay.get('first_seen'):
                relay['first_seen_date_escaped'] = relay['first_seen'][:10]
            
            if relay.get('last_seen'):
                relay['last_seen_date_escaped'] = relay['last_seen'][:10]
            
            # Existing IP parsing
            if relay.get('or_addresses'):
                if isinstance(relay['or_addresses'], list) and relay['or_addresses']:
                    relay['ip_address'] = relay['or_addresses'][0].split(':')[0]
                else:
                    relay['ip_address'] = 'Unknown'
            
            # Existing field escaping and truncation
            if relay.get('nickname'):
                relay['nickname_escaped'] = str(escape(relay['nickname']))
                relay['nickname_truncated'] = relay['nickname'][:20] + ('...' if len(relay['nickname']) > 20 else '')
            
            if relay.get('as_name'):
                relay['as_name_escaped'] = str(escape(relay['as_name']))
                relay['as_name_truncated'] = relay['as_name'][:30] + ('...' if len(relay['as_name']) > 30 else '')
            
            if relay.get('platform'):
                relay['platform_escaped'] = str(escape(relay['platform']))
                relay['platform_truncated'] = relay['platform'][:15] + ('...' if len(relay['platform']) > 15 else '')
            
            # Existing AROI and contact processing
            if relay.get('aroi_domain'):
                relay['aroi_domain_escaped'] = str(escape(relay['aroi_domain']))
            
            if relay.get('contact'):
                relay['contact_escaped'] = str(escape(relay['contact']))
            
            # Existing date processing
            if relay.get('first_seen'):
                date_parts = relay['first_seen'][:10].split('-')
                relay['first_seen_year'] = date_parts[0]
                relay['first_seen_month'] = date_parts[1] 
                relay['first_seen_day'] = date_parts[2]
            
            if relay.get('last_restarted'):
                relay['last_restarted_date'] = relay['last_restarted'][:10]
            
            # Existing flag processing
            if relay.get('flags'):
                relay['flags_escaped'] = [str(escape(flag)) for flag in relay['flags']]
                relay['flags_lower_escaped'] = [str(escape(flag.lower())) for flag in relay['flags']]
            
            # NEW OPTIMIZATION #2: Pre-compute HTML links and complex template elements
            relay['precomputed_html'] = {}
            
            # Pre-compute complete relay nickname cell
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
            
            # Pre-compute AROI cell
            if relay.get('aroi_domain') and relay['aroi_domain'] != 'none' and relay['aroi_domain'] != '':
                relay['precomputed_html']['aroi_cell'] = f'<a href="../../contact/{relay["contact_md5"]}/" title="{relay["aroi_domain_escaped"]}">{relay["aroi_domain_escaped"]}</a>'
            else:
                relay['precomputed_html']['aroi_cell'] = 'none'
            
            # Pre-compute IP address cell
            if relay.get('ip_address') and relay['ip_address'] != 'Unknown':
                relay['precomputed_html']['ip_cell'] = f'<a href="https://bgp.tools/prefix/{escape(relay["ip_address"])}">{escape(relay["ip_address"])}</a>'
            else:
                relay['precomputed_html']['ip_cell'] = 'Unknown'
            
            # Pre-compute AS number cell
            if relay.get('as'):
                relay['precomputed_html']['as_cell'] = f'<a href="../../as/{escape(relay["as"])}/">{escape(relay["as"])}</a>'
            else:
                relay['precomputed_html']['as_cell'] = 'Unknown'
            
            # Pre-compute AS name cell
            if relay.get('as_name') and relay.get('as'):
                relay['precomputed_html']['as_name_cell'] = f'<a href="https://bgp.tools/{escape(relay["as"])}" title="{relay["as_name_escaped"]}">{relay["as_name_truncated"]}</a>'
            else:
                relay['precomputed_html']['as_name_cell'] = 'Unknown'
            
            # Pre-compute country cell
            if relay.get('country') and relay.get('country_name'):
                img_tag = f'<img src="../../static/images/cc/{escape(relay["country"])}.png" title="{escape(relay["country_name"])}" alt="{escape(relay["country_name"])}">'
                relay['precomputed_html']['country_cell'] = f'<a href="../../country/{escape(relay["country"])}/">{img_tag}</a>'
            else:
                relay['precomputed_html']['country_cell'] = 'X'
            
            # Pre-compute platform cell
            if relay.get('platform'):
                relay['precomputed_html']['platform_cell'] = f'<a href="../../platform/{escape(relay["platform"])}/">{relay["platform_truncated"]}</a>'
            else:
                relay['precomputed_html']['platform_cell'] = 'Unknown'
            
            # Pre-compute flags cell
            if relay.get('flags'):
                flag_images = []
                for flag in relay['flags']:
                    if flag != 'StaleDesc':
                        flag_lower = escape(flag.lower())
                        flag_escaped = escape(flag)
                        flag_img = f'<a href="../../flag/{flag_lower}/"><img src="../../static/images/flags/{flag_lower}.png" title="{flag_escaped}" alt="{flag_escaped}"></a>'
                        flag_images.append(flag_img)
                relay['precomputed_html']['flags_cell'] = ''.join(flag_images)
            else:
                relay['precomputed_html']['flags_cell'] = ''
            
            # Pre-compute first seen cell
            if relay.get('first_seen_date_escaped'):
                relay['precomputed_html']['first_seen_cell'] = f'<a href="../../first_seen/{relay["first_seen_date_escaped"]}/">{relay["first_seen_date_escaped"]}</a>'
            else:
                relay['precomputed_html']['first_seen_cell'] = 'Unknown'
        
        print(f"✅ Enhanced template preprocessing with HTML pre-computation completed for {len(self.json['relays'])} relays")'''
    
    # Read current file and replace the method
    with open('allium/lib/relays.py', 'r') as f:
        content = f.read()
    
    # Find and replace the _preprocess_template_data method
    pattern = r'    def _preprocess_template_data\(self\):.*?(?=\n    def |\n\nclass |\Z)'
    new_content = re.sub(pattern, enhanced_method, content, flags=re.DOTALL)
    
    with open('allium/lib/relays.py', 'w') as f:
        f.write(new_content)
    
    print("✅ Applied optimization #2")

def apply_optimization_3():
    """Apply optimization #3: Template Loop Simplification"""
    print("🔧 Applying Optimization #3: Template Loop Simplification")
    
    # Backup original template
    shutil.copy('allium/templates/relay-list.html', 'allium/templates/relay-list.html.opt3_backup')
    
    # Simplified template using pre-computed values
    simplified_template = '''{% from "macros.html" import navigation %}
{% extends "skeleton.html" -%}
{% block title -%}
    Tor Relays
{% endblock -%}
{% block body -%}
<h2>
{% block header -%}
{% endblock -%}
</h2>

{% block navigation -%}
{% endblock -%}

<p>
{% block description -%}
{% endblock -%}
</p>

<p class="text-muted" style="margin-bottom: 15px;">
<small>Last updated: {{ relays.timestamp }}. Refreshed every 30 minutes from the Tor directory authorities via <a href="https://onionoo.torproject.org/">Tor Project's onionoo API</a>.</small>
</p>

<table class="table table-condensed">
<tr>
    <th></th>
    <th>Nickname</th>
    <th><a href="https://nusenu.github.io/ContactInfo-Information-Sharing-Specification/" target="_blank" title="Autonomous Relay Operator Identifier - unverified">AROI</a></th>
    <th>Contact</th>
    <th>BW</th>
    {% if key and not is_index -%}
    <th title="Bandwidth measured by >=3 bandwidth authorities">BW Measured</th>
    {% endif -%}
    <th class="visible-md visible-lg">IP Address</th>
    <th>AS Number</th>
    <th>AS Name</th>
    <th>Country</th>
    <th>Platform</th>
    <th class="visible-md visible-lg">Flags</th>
    <th class="visible-md visible-lg">First Seen</th>
    {% if key and not is_index -%}
    <th class="visible-md visible-lg">Last Restarted</th>
    {% endif -%}
</tr>
<tbody>
    {% if is_index -%}
	{% set relay_list = relays.json['relay_subset'][:500] -%}
    {% else -%}
	{% set relay_list = relays.json['relay_subset'] -%}
    {% endif -%}
    {% for relay in relay_list -%}
	<tr>
	    {% if relay['running'] -%}
		<td><span class="circle circle-online" title="This relay is online"></span></td>
	    {% else -%}
		<td><span class="circle circle-offline" title="This relay is offline"></span></td>
	    {% endif -%}
	    
	    <td title="{{ relay['nickname_escaped'] }}">{{ relay['precomputed_html']['nickname_cell'] }}</td>
	    
	    {% if key != 'contact' -%}
		<td>{{ relay['precomputed_html']['aroi_cell'] }}</td>
		<td>{{ relay['precomputed_html']['contact_cell'] }}</td>
	    {% else -%}
		<td>{{ relay['precomputed_html']['aroi_cell'] }}</td>
		<td title="{{ relay['contact_escaped'] }}"><span class="contact-text">{{ relay['contact_escaped'] }}</span></td>
	    {% endif -%}
	    
	    <td>{{ relay['obs_bandwidth_with_unit'] }}</td>
	    
	    {% if key and not is_index -%}
		<td title=">=3 bandwidth authorities have measured">
		    {% if relay['measured'] is not none -%}
		        {% if relay['measured'] -%}Yes{% else -%}No{% endif -%}
		    {% else -%}
		        unknown
		    {% endif -%}
		</td>
	    {% endif -%}
	    
	    <td class="visible-md visible-lg">{{ relay['precomputed_html']['ip_cell'] }}</td>
	    
	    {% if key != 'as' -%}
		<td>{{ relay['precomputed_html']['as_cell'] }}</td>
	    {% else -%}
		<td>{{ relay['as']|escape }}</td>
	    {% endif -%}
	    
	    <td>{{ relay['precomputed_html']['as_name_cell'] }}</td>
	    
	    {% if key != 'country' -%}
		<td>{{ relay['precomputed_html']['country_cell'] }}</td>
	    {% else -%}
		<td>{{ relay['precomputed_html']['country_cell'] }} {{ relay['country_name']|escape }}</td>
	    {% endif -%}
	    
	    {% if key != 'platform' -%}
		<td>{{ relay['precomputed_html']['platform_cell'] }}</td>
	    {% else -%}
		<td>{{ relay['platform_truncated'] }}</td>
	    {% endif -%}
	    
	    <td class="visible-md visible-lg">{{ relay['precomputed_html']['flags_cell'] }}</td>
	    
	    {% if key != 'first_seen' -%}
		<td class="visible-md visible-lg">{{ relay['precomputed_html']['first_seen_cell'] }}</td>
	    {% else -%}
		<td class="visible-md visible-lg">{{ relay['first_seen_date_escaped'] }}</td>
	    {% endif -%}
	    
	    {% if key and not is_index -%}
		<td class="visible-md visible-lg" title="{{ relay['last_restarted_date']|escape }}">
		    {{ relay['last_restarted_ago'] }}
		</td>
	    {% endif -%}
	</tr>
	{% endfor -%}
    </tbody>
</table>
{% endblock -%}
'''
    
    with open('allium/templates/relay-list.html', 'w') as f:
        f.write(simplified_template)
    
    print("✅ Applied optimization #3")

def restore_all_backups():
    """Restore all original files"""
    backup_files = [
        ('allium/lib/relays.py.opt2_backup', 'allium/lib/relays.py'),
        ('allium/lib/relays.py.opt3_backup', 'allium/lib/relays.py'),
        ('allium/templates/relay-list.html.opt3_backup', 'allium/templates/relay-list.html'),
    ]
    
    for backup, original in backup_files:
        if os.path.exists(backup):
            shutil.copy(backup, original)
            os.remove(backup)

def run_optimization_tests():
    """Run all optimization tests systematically"""
    print("🚀 STANDALONE OPTIMIZATION TESTING FRAMEWORK")
    print("="*80)
    print("Testing optimizations #2, #3, and #4 with systematic measurements")
    print("="*80 + "\n")
    
    results = {}
    
    # Ensure we start with clean slate
    restore_all_backups()
    
    # Test 1: Baseline measurement
    print("🔧 MEASURING BASELINE PERFORMANCE...")
    baseline = measure_performance_via_subprocess("baseline")
    if not baseline:
        print("❌ Baseline measurement failed")
        return
    
    results['baseline'] = baseline
    
    # Test 2: Optimization #2 - Bulk Context Optimization
    print("\n" + "="*60)
    print("🧪 TESTING OPTIMIZATION #2: BULK CONTEXT OPTIMIZATION")
    print("="*60)
    
    try:
        apply_optimization_2()
        opt2_result = measure_performance_via_subprocess("optimization_2")
        
        if opt2_result and baseline['family_time'] and opt2_result['family_time']:
            improvement = (baseline['family_time'] - opt2_result['family_time']) / baseline['family_time'] * 100
            
            print(f"\n📊 OPTIMIZATION #2 RESULTS:")
            print(f"   Baseline:  {baseline['family_time']:.2f}s ({baseline['family_pages']} pages)")
            print(f"   Optimized: {opt2_result['family_time']:.2f}s ({opt2_result['family_pages']} pages)")
            print(f"   Improvement: {improvement:.1f}%")
            
            if improvement > 5:
                print("   ✅ SIGNIFICANT BENEFIT CONFIRMED")
                results['optimization_2'] = {'result': opt2_result, 'improvement': improvement, 'beneficial': True}
            else:
                print("   ❌ NO SIGNIFICANT BENEFIT")
                results['optimization_2'] = {'result': opt2_result, 'improvement': improvement, 'beneficial': False}
        else:
            print("   ❌ Could not measure optimization #2 properly")
            results['optimization_2'] = {'error': 'measurement_failed'}
            
    except Exception as e:
        print(f"❌ Optimization #2 failed: {e}")
        results['optimization_2'] = {'error': str(e)}
    finally:
        # Restore original for next test
        if os.path.exists('allium/lib/relays.py.opt2_backup'):
            shutil.copy('allium/lib/relays.py.opt2_backup', 'allium/lib/relays.py')
    
    # Test 3: Optimization #3 - Template Simplification
    print("\n" + "="*60)
    print("🧪 TESTING OPTIMIZATION #3: TEMPLATE SIMPLIFICATION")
    print("="*60)
    
    try:
        # Apply both #2 and #3 together since #3 depends on #2's pre-computed values
        apply_optimization_2()
        apply_optimization_3()
        opt3_result = measure_performance_via_subprocess("optimization_3")
        
        if opt3_result and baseline['family_time'] and opt3_result['family_time']:
            improvement = (baseline['family_time'] - opt3_result['family_time']) / baseline['family_time'] * 100
            
            print(f"\n📊 OPTIMIZATION #3 RESULTS:")
            print(f"   Baseline:  {baseline['family_time']:.2f}s ({baseline['family_pages']} pages)")
            print(f"   Optimized: {opt3_result['family_time']:.2f}s ({opt3_result['family_pages']} pages)")
            print(f"   Improvement: {improvement:.1f}%")
            
            if improvement > 5:
                print("   ✅ SIGNIFICANT BENEFIT CONFIRMED")
                results['optimization_3'] = {'result': opt3_result, 'improvement': improvement, 'beneficial': True}
            else:
                print("   ❌ NO SIGNIFICANT BENEFIT")
                results['optimization_3'] = {'result': opt3_result, 'improvement': improvement, 'beneficial': False}
        else:
            print("   ❌ Could not measure optimization #3 properly")
            results['optimization_3'] = {'error': 'measurement_failed'}
            
    except Exception as e:
        print(f"❌ Optimization #3 failed: {e}")
        results['optimization_3'] = {'error': str(e)}
    finally:
        # Restore originals
        restore_all_backups()
    
    # Test 4: Check shared environment (should already be optimized)
    print("\n" + "="*60)
    print("🧪 TESTING OPTIMIZATION #4: SHARED ENVIRONMENT")
    print("="*60)
    
    # Check if shared environment is already implemented
    with open('allium/lib/relays.py', 'r') as f:
        content = f.read()
    
    if 'ENV = Environment(' in content:
        print("✅ Shared Environment optimization already implemented")
        print("🔍 Current implementation uses single Environment instance")
        results['optimization_4'] = {'already_optimized': True, 'beneficial': True}
    else:
        print("⚠️  Shared Environment not properly implemented")
        results['optimization_4'] = {'not_implemented': True, 'beneficial': False}
    
    # Final summary
    print("\n" + "="*80)
    print("📋 OPTIMIZATION TESTING SUMMARY")
    print("="*80)
    
    if baseline['family_time'] and baseline['family_pages']:
        print(f"🔧 Baseline: {baseline['family_time']:.2f}s for {baseline['family_pages']} family pages")
        print(f"   Average: {baseline['family_time']/baseline['family_pages']*1000:.1f}ms per page")
    
    beneficial_optimizations = []
    
    for opt_name, opt_data in results.items():
        if opt_name == 'baseline':
            continue
            
        if isinstance(opt_data, dict):
            if opt_data.get('beneficial'):
                if 'improvement' in opt_data:
                    print(f"✅ {opt_name}: {opt_data['improvement']:.1f}% improvement - BENEFICIAL")
                    beneficial_optimizations.append(opt_name)
                else:
                    print(f"✅ {opt_name}: Already optimized - BENEFICIAL")
                    beneficial_optimizations.append(opt_name)
            elif 'error' in opt_data:
                print(f"❌ {opt_name}: Failed - {opt_data['error']}")
            else:
                print(f"❌ {opt_name}: No significant benefit")
        else:
            print(f"❓ {opt_name}: Unknown result")
    
    print(f"\n🎯 BENEFICIAL OPTIMIZATIONS: {len(beneficial_optimizations)}/3")
    for opt in beneficial_optimizations:
        print(f"   ✅ {opt}")
    
    # Save results
    with open('optimization_test_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📁 Detailed results saved to optimization_test_results.json")
    return results

if __name__ == "__main__":
    run_optimization_tests() 