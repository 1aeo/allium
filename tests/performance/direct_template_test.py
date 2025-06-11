#!/usr/bin/env python3
"""Direct template rendering performance test."""

import time
import sys
import os
import tempfile
import shutil
from jinja2 import Environment, FileSystemLoader

def test_template_rendering_directly():
    """Test template rendering performance directly"""
    print("🧪 DIRECT TEMPLATE RENDERING TEST")
    print("="*50)
    
    # Set up Jinja2 environment
    env = Environment(
        loader=FileSystemLoader('allium/templates'),
        trim_blocks=True,
        lstrip_blocks=True
    )
    
    # Create mock relay data
    mock_relays = []
    for i in range(100):  # Create 100 mock relays for testing
        mock_relays.append({
            'fingerprint': f'ABCD{i:016X}',
            'nickname': f'TestRelay{i}',
            'running': True,
            'effective_family': [f'ABCD{i:016X}', f'ABCD{(i+1):016X}'] if i % 3 == 0 else [f'ABCD{i:016X}'],
            'contact': f'contact{i}@example.com',
            'contact_md5': f'hash{i:016x}',
            'aroi_domain': 'example.com' if i % 2 == 0 else 'none',
            'observed_bandwidth': 1000000 * (i + 1),
            'obs_bandwidth_with_unit': f'{(i+1)} MB/s',
            'as': f'{1000 + i}',
            'as_name': f'AS Provider {i}',
            'country': 'US',
            'country_name': 'United States',
            'platform': f'Tor 0.4.{i % 10}.0',
            'flags': ['Running', 'V2Dir'] + (['Guard'] if i % 2 == 0 else []),
            'first_seen': f'2023-{(i % 12) + 1:02d}-01 00:00:00',
            'first_seen_date_escaped': f'2023-{(i % 12) + 1:02d}-01',
            'or_addresses': [f'192.168.1.{i % 254}:9001'],
            'ip_address': f'192.168.1.{i % 254}',
            'last_restarted': f'2024-{(i % 12) + 1:02d}-01 00:00:00',
            'last_restarted_ago': f'{i} days ago',
            'last_restarted_date': f'2024-{(i % 12) + 1:02d}-01',
            'measured': True if i % 3 == 0 else False,
            # Pre-computed values (existing optimization)
            'nickname_escaped': f'TestRelay{i}',
            'nickname_truncated': f'TestRelay{i}',
            'contact_escaped': f'contact{i}@example.com',
            'aroi_domain_escaped': 'example.com' if i % 2 == 0 else 'none',
            'as_name_escaped': f'AS Provider {i}',
            'as_name_truncated': f'AS Provider {i}',
            'platform_escaped': f'Tor 0.4.{i % 10}.0',
            'platform_truncated': f'Tor 0.4.{i % 10}.0',
        })
    
    # Mock relay_set object
    class MockRelaySet:
        def __init__(self):
            self.json = {'relay_subset': mock_relays}
            self.timestamp = '2024-01-15 12:00:00'
    
    relays = MockRelaySet()
    
    # Load template
    template = env.get_template('relay-list.html')
    
    # Test current template (baseline)
    print("📊 Testing baseline template performance...")
    start_time = time.time()
    
    for _ in range(10):  # Render 10 times for better measurement
        rendered = template.render(
            relays=relays,
            key='family',
            value='test_family',
            is_index=False
        )
    
    baseline_time = time.time() - start_time
    print(f"✅ Baseline: {baseline_time:.3f}s for 10 renders ({baseline_time/10*1000:.1f}ms per render)")
    
    # Now test with HTML pre-computation optimization
    print("\n🔧 Applying HTML pre-computation optimization...")
    
    # Add precomputed HTML to mock data
    for relay in mock_relays:
        relay['precomputed_html'] = {}
        
        # Pre-compute nickname cell
        nickname_trunc = relay['nickname_truncated']
        relay_link = f'<a href="../../relay/{relay["fingerprint"]}/">{nickname_trunc}</a>'
        
        if len(relay['effective_family']) > 1:
            family_link = f' (<a href="../../family/{relay["fingerprint"]}/">{len(relay["effective_family"])}</a>)'
            relay['precomputed_html']['nickname_cell'] = relay_link + family_link
        else:
            relay['precomputed_html']['nickname_cell'] = relay_link
        
        # Pre-compute contact cell
        if relay.get('contact'):
            contact_esc = relay['contact_escaped']
            relay['precomputed_html']['contact_cell'] = f'<a href="../../contact/{relay["contact_md5"]}/" title="{contact_esc}" class="contact-text">{contact_esc}</a>'
        else:
            relay['precomputed_html']['contact_cell'] = '<span title="none">none</span>'
        
        # Pre-compute AROI cell
        if relay.get('aroi_domain') and relay['aroi_domain'] != 'none':
            aroi_esc = relay['aroi_domain_escaped']
            relay['precomputed_html']['aroi_cell'] = f'<a href="../../contact/{relay["contact_md5"]}/" title="{aroi_esc}">{aroi_esc}</a>'
        else:
            relay['precomputed_html']['aroi_cell'] = 'none'
    
    # Create optimized template
    optimized_template_content = '''{% from "macros.html" import navigation %}
{% extends "skeleton.html" -%}
{% block title -%}
    Tor Relays
{% endblock -%}
{% block body -%}
<h2>Test Family</h2>

<table class="table table-condensed">
<tr>
    <th></th>
    <th>Nickname</th>
    <th>AROI</th>
    <th>Contact</th>
    <th>BW</th>
</tr>
<tbody>
    {% for relay in relays.json['relay_subset'] -%}
	<tr>
	    {% if relay['running'] -%}
		<td><span class="circle circle-online" title="This relay is online"></span></td>
	    {% else -%}
		<td><span class="circle circle-offline" title="This relay is offline"></span></td>
	    {% endif -%}
	    
	    <td title="{{ relay['nickname_escaped'] }}">
		{{ relay['precomputed_html']['nickname_cell'] }}
	    </td>
	    
	    <td>{{ relay['precomputed_html']['aroi_cell'] }}</td>
	    <td>{{ relay['precomputed_html']['contact_cell'] }}</td>
	    <td>{{ relay['obs_bandwidth_with_unit'] }}</td>
	</tr>
	{% endfor -%}
    </tbody>
</table>
{% endblock -%}
'''
    
    # Create temporary template file
    temp_template_path = 'allium/templates/test-optimized.html'
    with open(temp_template_path, 'w') as f:
        f.write(optimized_template_content)
    
    try:
        # Load optimized template
        optimized_template = env.get_template('test-optimized.html')
        
        # Test optimized template
        print("📊 Testing optimized template performance...")
        start_time = time.time()
        
        for _ in range(10):  # Render 10 times for better measurement
            rendered = optimized_template.render(
                relays=relays,
                key='family',
                value='test_family',
                is_index=False
            )
        
        optimized_time = time.time() - start_time
        print(f"✅ Optimized: {optimized_time:.3f}s for 10 renders ({optimized_time/10*1000:.1f}ms per render)")
        
        # Calculate improvement
        improvement = (baseline_time - optimized_time) / baseline_time * 100
        print(f"\n📈 RESULTS:")
        print(f"   Baseline:  {baseline_time:.3f}s")
        print(f"   Optimized: {optimized_time:.3f}s")
        print(f"   Improvement: {improvement:.1f}%")
        
        if improvement > 5:
            print("   ✅ OPTIMIZATION IS BENEFICIAL")
        else:
            print("   ❌ OPTIMIZATION IS NOT BENEFICIAL")
            
    finally:
        # Clean up temp file
        if os.path.exists(temp_template_path):
            os.remove(temp_template_path)

def test_jinja2_operations():
    """Test individual Jinja2 operations to identify bottlenecks"""
    print("\n" + "="*50)
    print("🔬 JINJA2 OPERATION ANALYSIS")
    print("="*50)
    
    # Set up Jinja2 environment
    env = Environment()
    
    # Test data
    test_relay = {
        'fingerprint': 'ABCD1234567890ABCD1234567890ABCD12345678',
        'nickname': 'TestRelay',
        'effective_family': ['ABCD1234567890ABCD1234567890ABCD12345678', 'EFGH1234567890EFGH1234567890EFGH12345678'],
        'contact': 'test@example.com',
        'contact_md5': 'abcd1234567890abcd1234567890abcd12',
        'aroi_domain': 'example.com'
    }
    
    # Test 1: String escaping
    template1_str = "{{ relay['nickname']|escape }}"
    template1 = env.from_string(template1_str)
    
    start = time.time()
    for _ in range(1000):
        template1.render(relay=test_relay)
    escape_time = time.time() - start
    
    # Test 2: String truncation
    template2_str = "{{ relay['nickname']|truncate(20) }}"
    template2 = env.from_string(template2_str)
    
    start = time.time()
    for _ in range(1000):
        template2.render(relay=test_relay)
    truncate_time = time.time() - start
    
    # Test 3: Complex conditionals
    template3_str = """{% if relay['effective_family'] is defined and relay['effective_family']|length > 1 -%}
 (<a href="../../family/{{ relay['fingerprint']|escape }}/">{{ relay['effective_family']|length }}</a>)
{% endif -%}"""
    template3 = env.from_string(template3_str)
    
    start = time.time()
    for _ in range(1000):
        template3.render(relay=test_relay)
    conditional_time = time.time() - start
    
    # Test 4: Pre-computed value
    test_relay['precomputed_html_cell'] = ' (<a href="../../family/ABCD1234567890ABCD1234567890ABCD12345678/">2</a>)'
    template4_str = "{{ relay['precomputed_html_cell'] }}"
    template4 = env.from_string(template4_str)
    
    start = time.time()
    for _ in range(1000):
        template4.render(relay=test_relay)
    precomputed_time = time.time() - start
    
    print(f"🔍 Operation performance (1000 iterations):")
    print(f"   String escape:       {escape_time:.3f}s")
    print(f"   String truncate:     {truncate_time:.3f}s") 
    print(f"   Complex conditional: {conditional_time:.3f}s")
    print(f"   Pre-computed value:  {precomputed_time:.3f}s")
    
    print(f"\n📊 Relative performance:")
    print(f"   Escape vs Pre-computed:     {escape_time/precomputed_time:.1f}x slower")
    print(f"   Truncate vs Pre-computed:   {truncate_time/precomputed_time:.1f}x slower")
    print(f"   Conditional vs Pre-computed: {conditional_time/precomputed_time:.1f}x slower")

if __name__ == "__main__":
    test_template_rendering_directly()
    test_jinja2_operations() 