#!/usr/bin/env python3
"""
Onionoo Uptime Flag Data Analysis
Fetches all uptime data and analyzes 6-month vs 5-year flag data availability
"""

import json
import urllib.request
import urllib.error
from collections import defaultdict, Counter
import random

def fetch_onionoo_uptime_data():
    """
    Fetch all uptime data from Onionoo API
    
    Returns:
        dict: JSON response from Onionoo uptime API
    """
    url = "https://onionoo.torproject.org/uptime"
    
    try:
        print(f"Fetching data from: {url}")
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            print(f"✓ Successfully fetched data for {len(data.get('relays', []))} relays")
            return data
    except urllib.error.URLError as e:
        print(f"✗ Error fetching data: {e}")
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None

def analyze_flag_uptime_availability(uptime_data):
    """
    Analyze flag uptime data availability across different time periods
    
    Args:
        uptime_data (dict): Onionoo uptime API response
        
    Returns:
        dict: Analysis results
    """
    if not uptime_data or 'relays' not in uptime_data:
        return None
    
    results = {
        'total_relays': len(uptime_data['relays']),
        'relays_with_flags': 0,
        'flag_periods': defaultdict(lambda: defaultdict(int)),
        'flag_examples': defaultdict(lambda: defaultdict(list)),
        'period_summary': defaultdict(int),
        'relay_samples': []
    }
    
    # Available time periods we're looking for
    target_periods = ['1_month', '6_months', '1_year', '5_years']
    
    for relay in uptime_data['relays']:
        fingerprint = relay.get('fingerprint', 'Unknown')
        
        # Check if relay has flag data
        if 'flags' in relay:
            results['relays_with_flags'] += 1
            
            # Analyze each flag
            for flag_name, flag_data in relay['flags'].items():
                if isinstance(flag_data, dict):
                    # Check each time period
                    for period in target_periods:
                        if period in flag_data:
                            period_data = flag_data[period]
                            # Check if there's actual values data
                            if isinstance(period_data, dict) and 'values' in period_data:
                                values = period_data['values']
                                if values and any(v is not None for v in values):
                                    results['flag_periods'][flag_name][period] += 1
                                    results['period_summary'][period] += 1
                                    
                                    # Store examples (limit to 3 per flag/period)
                                    if len(results['flag_examples'][flag_name][period]) < 3:
                                        non_null_values = [v for v in values if v is not None]
                                        if non_null_values:
                                            avg_value = sum(non_null_values) / len(non_null_values) / 999 * 100
                                            results['flag_examples'][flag_name][period].append({
                                                'fingerprint': fingerprint[:12] + '...',
                                                'total_values': len(values),
                                                'non_null_values': len(non_null_values),
                                                'avg_uptime_pct': round(avg_value, 1)
                                            })
        
        # Store sample relay data for detailed analysis
        if len(results['relay_samples']) < 5:
            sample_data = {
                'fingerprint': fingerprint[:12] + '...',
                'has_flags': 'flags' in relay,
                'flag_summary': {}
            }
            
            if 'flags' in relay:
                for flag_name, flag_data in relay['flags'].items():
                    if isinstance(flag_data, dict):
                        periods_available = [p for p in target_periods if p in flag_data and 
                                           isinstance(flag_data[p], dict) and 'values' in flag_data[p]]
                        sample_data['flag_summary'][flag_name] = periods_available
            
            results['relay_samples'].append(sample_data)
    
    return results

def print_analysis_results(results):
    """
    Print formatted analysis results
    
    Args:
        results (dict): Analysis results from analyze_flag_uptime_availability
    """
    if not results:
        print("No results to display")
        return
    
    print("\n" + "="*80)
    print("ONIONOO UPTIME FLAG DATA ANALYSIS")
    print("="*80)
    
    print(f"\n📊 OVERALL STATISTICS")
    print(f"Total relays in dataset: {results['total_relays']:,}")
    print(f"Relays with flag data: {results['relays_with_flags']:,} ({results['relays_with_flags']/results['total_relays']*100:.1f}%)")
    
    print(f"\n⏰ TIME PERIOD AVAILABILITY SUMMARY")
    print("-" * 50)
    for period, count in sorted(results['period_summary'].items()):
        print(f"{period:12s}: {count:6,} flag instances")
    
    # Calculate 6M vs 5Y comparison
    six_month_count = results['period_summary']['6_months']
    five_year_count = results['period_summary']['5_years']
    if five_year_count > 0:
        ratio = six_month_count / five_year_count
        print(f"\n📈 6-month vs 5-year ratio: {ratio:.2f} ({six_month_count:,} / {five_year_count:,})")
    
    print(f"\n🏷️ FLAG-SPECIFIC BREAKDOWN")
    print("-" * 70)
    print(f"{'Flag':<15} {'1M':<6} {'6M':<6} {'1Y':<6} {'5Y':<6} {'6M/5Y Ratio':<12}")
    print("-" * 70)
    
    for flag_name in sorted(results['flag_periods'].keys()):
        periods = results['flag_periods'][flag_name]
        ratio_6m_5y = periods['6_months'] / periods['5_years'] if periods['5_years'] > 0 else 0
        print(f"{flag_name:<15} {periods['1_month']:<6} {periods['6_months']:<6} {periods['1_year']:<6} {periods['5_years']:<6} {ratio_6m_5y:<12.2f}")
    
    print(f"\n📋 REAL DATA EXAMPLES")
    print("-" * 50)
    
    # Show examples for key flags and periods
    key_flags = ['Running', 'Guard', 'Exit', 'Fast', 'Stable']
    key_periods = ['6_months', '5_years']
    
    for flag in key_flags:
        if flag in results['flag_examples']:
            print(f"\n🔍 {flag} Flag Examples:")
            for period in key_periods:
                if period in results['flag_examples'][flag] and results['flag_examples'][flag][period]:
                    print(f"  {period}:")
                    for example in results['flag_examples'][flag][period]:
                        print(f"    {example['fingerprint']} - {example['avg_uptime_pct']:.1f}% avg uptime "
                              f"({example['non_null_values']}/{example['total_values']} data points)")
    
    print(f"\n🔬 SAMPLE RELAY ANALYSIS")
    print("-" * 50)
    for i, sample in enumerate(results['relay_samples'], 1):
        print(f"\nSample Relay #{i}: {sample['fingerprint']}")
        print(f"  Has flags: {sample['has_flags']}")
        if sample['flag_summary']:
            for flag, periods in sample['flag_summary'].items():
                print(f"  {flag}: {periods}")

def main():
    """
    Main function to run the analysis
    """
    print("Onionoo Uptime Flag Data Analysis")
    print("=================================")
    
    # Fetch data
    uptime_data = fetch_onionoo_uptime_data()
    if not uptime_data:
        print("Failed to fetch data. Exiting.")
        return
    
    # Analyze data
    print("\nAnalyzing flag uptime availability...")
    results = analyze_flag_uptime_availability(uptime_data)
    
    if not results:
        print("Failed to analyze data. Exiting.")
        return
    
    # Print results
    print_analysis_results(results)
    
    # Additional insights
    print(f"\n💡 KEY INSIGHTS")
    print("-" * 30)
    
    six_month_total = results['period_summary']['6_months']
    five_year_total = results['period_summary']['5_years']
    
    if six_month_total < five_year_total:
        difference = five_year_total - six_month_total
        print(f"• 6-month data is less available: {difference:,} fewer instances than 5-year")
        print(f"• This represents a {(1 - six_month_total/five_year_total)*100:.1f}% reduction")
    elif six_month_total > five_year_total:
        difference = six_month_total - five_year_total
        print(f"• 6-month data is more available: {difference:,} more instances than 5-year")
        print(f"• This represents a {(six_month_total/five_year_total - 1)*100:.1f}% increase")
    else:
        print(f"• 6-month and 5-year data availability is equal")
    
    print(f"• {results['relays_with_flags']} out of {results['total_relays']} relays have flag uptime data")

if __name__ == "__main__":
    main()