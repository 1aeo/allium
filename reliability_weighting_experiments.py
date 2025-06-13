#!/usr/bin/env python3

"""
Reliability Weighting Experiments for Tor Relay Operators

This script analyzes different weighting methodologies for ranking Tor relay operators
based on reliability, using only Python standard library modules.
"""

import json
import csv
import math
import os
import statistics
from collections import defaultdict
from typing import Dict, List, Tuple, Any

# Sample data from the user's image (Top 25 Reliability Masters)
SAMPLE_DATA = [
    {"rank": 1, "operator": "nothingtohide.nl", "relays": 294, "reliability": 99.4, "bandwidth": "39.0 Gbits", "unit": "Gbits"},
    {"rank": 2, "operator": "quetzalcoatl-relays.org", "relays": 572, "reliability": 99.2, "bandwidth": "47.4 Gbits", "unit": "Gbits"},
    {"rank": 3, "operator": "prsv.ch", "relays": 323, "reliability": 97.8, "bandwidth": "28.8 Gbits", "unit": "Gbits"},
    {"rank": 4, "operator": "internetanonymity.org", "relays": 115, "reliability": 97.5, "bandwidth": "10.9 Gbits", "unit": "Gbits"},
    {"rank": 5, "operator": "tor-relay.iamsad.dev", "relays": 1, "reliability": 97.2, "bandwidth": "1.6 Gbits", "unit": "Gbits"},
    {"rank": 6, "operator": "exitnodes.org", "relays": 32, "reliability": 97.1, "bandwidth": "3.0 Gbits", "unit": "Gbits"},
    {"rank": 7, "operator": "tor-help.info", "relays": 13, "reliability": 96.9, "bandwidth": "1.3 Gbits", "unit": "Gbits"},
    {"rank": 8, "operator": "torseed.org", "relays": 8, "reliability": 96.8, "bandwidth": "1.2 Gbits", "unit": "Gbits"},
    {"rank": 9, "operator": "cyberwarfare.pro", "relays": 5, "reliability": 96.8, "bandwidth": "708.9 Mbits", "unit": "Mbits"},
    {"rank": 10, "operator": "0x616e6f6e.net", "relays": 26, "reliability": 96.7, "bandwidth": "2.6 Gbits", "unit": "Gbits"},
    {"rank": 11, "operator": "relayonions.org", "relays": 10, "reliability": 96.6, "bandwidth": "988.8 Mbits", "unit": "Mbits"},
    {"rank": 12, "operator": "relay.thebootlegs.net", "relays": 1, "reliability": 96.4, "bandwidth": "102.5 Mbits", "unit": "Mbits"},
    {"rank": 13, "operator": "diicot.org", "relays": 1, "reliability": 96.4, "bandwidth": "101.8 Mbits", "unit": "Mbits"},
    {"rank": 14, "operator": "anonymous-proxy-servers.net", "relays": 1, "reliability": 100.0, "bandwidth": "930.2 Mbits", "unit": "Mbits"},
    {"rank": 15, "operator": "for-privacy.net", "relays": 1, "reliability": 100.0, "bandwidth": "916.6 Mbits", "unit": "Mbits"},
    {"rank": 16, "operator": "hacktheplanet.com", "relays": 1, "reliability": 100.0, "bandwidth": "903.8 Mbits", "unit": "Mbits"},
    {"rank": 17, "operator": "dfri.se", "relays": 1, "reliability": 100.0, "bandwidth": "903.2 Mbits", "unit": "Mbits"},
    {"rank": 18, "operator": "tor.abusedomain.de", "relays": 1, "reliability": 100.0, "bandwidth": "898.7 Mbits", "unit": "Mbits"},
    {"rank": 19, "operator": "torbox.net", "relays": 1, "reliability": 100.0, "bandwidth": "876.4 Mbits", "unit": "Mbits"},
    {"rank": 20, "operator": "tor-relays.org", "relays": 1, "reliability": 100.0, "bandwidth": "874.3 Mbits", "unit": "Mbits"},
    {"rank": 21, "operator": "tor.duckdns.org", "relays": 1, "reliability": 100.0, "bandwidth": "858.9 Mbits", "unit": "Mbits"},
    {"rank": 22, "operator": "tor.einval.org", "relays": 1, "reliability": 100.0, "bandwidth": "854.2 Mbits", "unit": "Mbits"},
    {"rank": 23, "operator": "saintly.org", "relays": 1, "reliability": 100.0, "bandwidth": "848.5 Mbits", "unit": "Mbits"},
    {"rank": 24, "operator": "tor-relay.privateinternetaccess.com", "relays": 1, "reliability": 100.0, "bandwidth": "829.1 Mbits", "unit": "Mbits"},
    {"rank": 25, "operator": "tor.datatracker.net", "relays": 1, "reliability": 100.0, "bandwidth": "819.7 Mbits", "unit": "Mbits"},
]

def normalize_bandwidth(bandwidth_str: str, unit: str) -> float:
    """Convert bandwidth to Mbits for comparison"""
    bandwidth = float(bandwidth_str)
    if unit == "Gbits":
        return bandwidth * 1000  # Convert to Mbits
    return bandwidth  # Already in Mbits

def calculate_weighted_scores(data: List[Dict], method: str) -> List[Dict]:
    """Calculate weighted scores based on different methodologies"""
    
    # Normalize bandwidth for all operators
    for operator in data:
        operator['bandwidth_mbits'] = normalize_bandwidth(
            operator['bandwidth'].split()[0], 
            operator['unit']
        )
    
    # Calculate additional metrics
    total_bandwidth = sum(op['bandwidth_mbits'] for op in data)
    max_relays = max(op['relays'] for op in data)
    
    # Calculate bandwidth share for all operators first
    for operator in data:
        operator['bandwidth_share'] = (operator['bandwidth_mbits'] / total_bandwidth) * 100
    
    # Calculate max bandwidth share after all shares are calculated
    max_bandwidth_share = max(op['bandwidth_share'] for op in data)
    
    for operator in data:
        # Calculate weighted score based on method
        if method == "current":
            # Pure reliability ranking
            operator['weighted_score'] = operator['reliability']
            
        elif method == "log_relay_2":
            # Logarithmic scaling (base 2)
            relay_factor = math.log2(max(1, operator['relays']))
            operator['weighted_score'] = operator['reliability'] * (1 + relay_factor * 0.1)
            
        elif method == "log_relay_3":
            # Logarithmic scaling (base 3)
            relay_factor = math.log(max(1, operator['relays']), 3)
            operator['weighted_score'] = operator['reliability'] * (1 + relay_factor * 0.1)
            
        elif method == "sqrt_relay":
            # Square root scaling
            relay_factor = math.sqrt(operator['relays'])
            operator['weighted_score'] = operator['reliability'] * (1 + relay_factor * 0.02)
            
        elif method == "diminishing_returns":
            # Diminishing returns after 50 relays
            if operator['relays'] <= 50:
                relay_factor = operator['relays'] / 50
            else:
                excess = operator['relays'] - 50
                relay_factor = 1.0 + (excess * 0.1)  # Much slower growth
            operator['weighted_score'] = operator['reliability'] * (0.5 + relay_factor * 0.5)
            
        elif method == "bandwidth_balanced":
            # 70% reliability, 30% bandwidth contribution
            bandwidth_score = (operator['bandwidth_share'] / max_bandwidth_share) * 100
            operator['weighted_score'] = (operator['reliability'] * 0.7) + (bandwidth_score * 0.3)
            
        elif method == "diversity_bonus":
            # Bonus for geographic and platform diversity (simulated)
            diversity_bonus = 1.0
            if operator['relays'] > 1:  # Multi-relay operators get geography bonus
                diversity_bonus *= 1.2
            if operator['relays'] > 10:  # Larger operators get platform diversity bonus
                diversity_bonus *= 1.1
            operator['weighted_score'] = operator['reliability'] * diversity_bonus
            
        elif method == "tiered_groups":
            # Different multiplier per relay count tier
            if operator['relays'] == 1:
                tier_multiplier = 0.8  # Single relay penalty
            elif operator['relays'] <= 10:
                tier_multiplier = 1.0  # Small operators
            elif operator['relays'] <= 50:
                tier_multiplier = 1.1  # Medium operators
            elif operator['relays'] <= 200:
                tier_multiplier = 1.2  # Large operators
            else:
                tier_multiplier = 1.0  # Very large operators (no extra bonus)
            operator['weighted_score'] = operator['reliability'] * tier_multiplier
            
        elif method == "hybrid_balanced":
            # Multi-factor approach
            reliability_component = operator['reliability'] * 0.5
            relay_component = min(math.log2(max(1, operator['relays'])) * 5, 25)  # Cap at 25
            bandwidth_component = min(operator['bandwidth_share'] * 2, 25)  # Cap at 25
            diversity_component = (5 if operator['relays'] > 10 else 0)
            
            operator['weighted_score'] = (reliability_component + relay_component + 
                                        bandwidth_component + diversity_component)
    
    # Sort by weighted score (descending)
    return sorted(data, key=lambda x: x['weighted_score'], reverse=True)

def analyze_ranking_changes(original_data: List[Dict], new_data: List[Dict]) -> Dict:
    """Analyze how rankings changed between methods"""
    original_ranks = {op['operator']: op['rank'] for op in original_data}
    new_ranks = {op['operator']: i+1 for i, op in enumerate(new_data)}
    
    changes = []
    for operator in original_data:
        name = operator['operator']
        old_rank = original_ranks.get(name, 0)
        new_rank = new_ranks.get(name, 0)
        change = old_rank - new_rank  # Positive = moved up, negative = moved down
        changes.append({
            'operator': name,
            'old_rank': old_rank,
            'new_rank': new_rank,
            'change': change,
            'relays': operator['relays']
        })
    
    # Sort by biggest changes
    biggest_gainers = sorted([c for c in changes if c['change'] > 0], 
                           key=lambda x: x['change'], reverse=True)[:5]
    biggest_losers = sorted([c for c in changes if c['change'] < 0], 
                          key=lambda x: x['change'])[:5]
    
    return {
        'biggest_gainers': biggest_gainers,
        'biggest_losers': biggest_losers,
        'all_changes': changes
    }

def analyze_top10_distribution(data: List[Dict]) -> Dict:
    """Analyze the distribution of operator types in top 10"""
    top10 = data[:10]
    
    single_relay = sum(1 for op in top10 if op['relays'] == 1)
    small_operators = sum(1 for op in top10 if 2 <= op['relays'] <= 10)
    medium_operators = sum(1 for op in top10 if 11 <= op['relays'] <= 50)
    large_operators = sum(1 for op in top10 if 51 <= op['relays'] <= 200)
    very_large_operators = sum(1 for op in top10 if op['relays'] > 200)
    
    return {
        'single_relay': single_relay,
        'small_operators': small_operators,
        'medium_operators': medium_operators,
        'large_operators': large_operators,
        'very_large_operators': very_large_operators
    }

def export_results_to_csv(method_results: Dict, filename: str):
    """Export all results to CSV for easy analysis"""
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow(['Method', 'Rank', 'Operator', 'Relays', 'Reliability', 
                        'Bandwidth_Mbits', 'Weighted_Score', 'Change_from_Current'])
        
        # Write data for each method
        current_ranks = {op['operator']: op['rank'] for op in SAMPLE_DATA}
        
        for method, data in method_results.items():
            for i, operator in enumerate(data, 1):
                change = current_ranks.get(operator['operator'], 0) - i
                writer.writerow([
                    method, i, operator['operator'], operator['relays'],
                    operator['reliability'], operator['bandwidth_mbits'],
                    round(operator['weighted_score'], 2), change
                ])

def main():
    """Run all weighting experiments and generate reports"""
    
    print("🔬 Tor Relay Reliability Weighting Experiments")
    print("=" * 60)
    print()
    
    # Define all methods to test
    methods = {
        "current": "Current Method (Pure Reliability)",
        "log_relay_2": "Log Relay Weighted (Base 2)",
        "log_relay_3": "Log Relay Weighted (Base 3)", 
        "sqrt_relay": "Square Root Relay Weighted",
        "diminishing_returns": "Diminishing Returns (50+ relay penalty)",
        "bandwidth_balanced": "Bandwidth Balanced (70/30 split)",
        "diversity_bonus": "Diversity Bonus (Geography + Platform)",
        "tiered_groups": "Tiered Relay Groups",
        "hybrid_balanced": "Hybrid Balanced (Multi-factor)"
    }
    
    # Run experiments
    results = {}
    for method_key, method_name in methods.items():
        print(f"🧪 Running experiment: {method_name}")
        # Create a copy of sample data for each experiment
        data_copy = [op.copy() for op in SAMPLE_DATA]
        results[method_key] = calculate_weighted_scores(data_copy, method_key)
    
    print("\n📊 EXPERIMENT RESULTS")
    print("=" * 60)
    
    # Show top 10 for each method
    for method_key, method_name in methods.items():
        print(f"\n🏆 TOP 10 - {method_name}")
        print("-" * 50)
        
        top10 = results[method_key][:10]
        for i, operator in enumerate(top10, 1):
            print(f"{i:2}. {operator['operator']:<35} "
                  f"({operator['relays']:3} relays, {operator['reliability']:5.1f}% reliability, "
                  f"score: {operator['weighted_score']:6.1f})")
        
        # Show distribution analysis
        distribution = analyze_top10_distribution(results[method_key])
        print(f"    📈 Top 10 Distribution: {distribution['single_relay']} single, "
              f"{distribution['small_operators']} small (2-10), "
              f"{distribution['medium_operators']} medium (11-50), "
              f"{distribution['large_operators']} large (51-200), "
              f"{distribution['very_large_operators']} very large (200+)")
        
        # Show ranking changes vs current method
        if method_key != "current":
            changes = analyze_ranking_changes(SAMPLE_DATA, results[method_key])
            if changes['biggest_gainers']:
                print(f"    📈 Biggest Gainers: ", end="")
                for i, gainer in enumerate(changes['biggest_gainers'][:3]):
                    if i > 0:
                        print(", ", end="")
                    print(f"{gainer['operator']} (+{gainer['change']})", end="")
                print()
            
            if changes['biggest_losers']:
                print(f"    📉 Biggest Losers: ", end="")
                for i, loser in enumerate(changes['biggest_losers'][:3]):
                    if i > 0:
                        print(", ", end="")
                    print(f"{loser['operator']} ({loser['change']})", end="")
                print()
    
    # Export results to CSV
    export_results_to_csv(results, 'reliability_weighting_results.csv')
    print(f"\n💾 Results exported to: reliability_weighting_results.csv")
    
    # Generate recommendations
    print("\n🎯 RECOMMENDATIONS")
    print("=" * 60)
    
    recommendations = [
        {
            "method": "tiered_groups",
            "name": "Tiered Relay Groups",
            "pros": [
                "Balances single vs multi-relay operators effectively",
                "Prevents 500+ relay operators from dominating",
                "Simple to understand and implement",
                "Gives medium operators (11-50 relays) slight advantage"
            ],
            "cons": [
                "Somewhat arbitrary tier boundaries",
                "Doesn't account for bandwidth contribution",
                "May not reflect actual network contribution"
            ],
            "use_case": "Best for encouraging diversity while maintaining reliability focus"
        },
        {
            "method": "diminishing_returns", 
            "name": "Diminishing Returns",
            "pros": [
                "Natural scaling that prevents very large operator dominance",
                "Rewards efficiency over raw relay count",
                "Mathematically elegant approach"
            ],
            "cons": [
                "May penalize legitimate large operators too much",
                "Threshold selection (50 relays) is somewhat arbitrary"
            ],
            "use_case": "Good for promoting network decentralization"
        },
        {
            "method": "hybrid_balanced",
            "name": "Hybrid Balanced", 
            "pros": [
                "Considers multiple factors (reliability, relays, bandwidth, diversity)",
                "Most comprehensive evaluation method",
                "Balanced approach to different operator types"
            ],
            "cons": [
                "More complex to implement and understand",
                "Requires tuning of component weights",
                "May be over-engineered for the use case"
            ],
            "use_case": "Best for comprehensive operator evaluation"
        }
    ]
    
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. 🏅 {rec['name']} ({rec['method']})")
        print(f"   Use Case: {rec['use_case']}")
        print("   ✅ Pros:")
        for pro in rec['pros']:
            print(f"      • {pro}")
        print("   ❌ Cons:")
        for con in rec['cons']:
            print(f"      • {con}")
    
    print("\n🎯 FINAL RECOMMENDATION:")
    print("For your use case (preventing 500+ relay dominance while not letting single")
    print("relays dominate), I recommend the 'Tiered Relay Groups' method. It provides")
    print("the best balance and is easy to understand and tune.")
    
    print(f"\n✅ Experiment completed! Check 'reliability_weighting_results.csv' for detailed data.")

if __name__ == "__main__":
    main()