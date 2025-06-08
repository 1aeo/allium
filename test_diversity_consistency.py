#!/usr/bin/env python3
"""
Test the updated diversity rating system for consistency across all three metrics.
"""

import sys
import os
sys.path.append('.')

from allium.lib.intelligence_engine import IntelligenceEngine

def test_diversity_consistency():
    """Test that all three diversity metrics use consistent great/good/poor ratings"""
    
    print("Testing diversity rating consistency...")
    
    # Test case 1: Single AS, single country, single platform/version (all Poor)
    relays_poor_data = {
        'relays': [
            {
                'fingerprint': 'A' * 40,
                'as_number': 12345,
                'country': 'us',
                'platform': 'Linux',
                'version': '0.4.7.8',
                'observed_bandwidth': 5000000,
                'consensus_weight': 1000
            }
        ],
        'sorted': {
            'contact': {
                'test_contact': {
                    'relays': [0],
                    'unique_as_count': 1,
                    'measured_count': 1
                }
            }
        },
        'network_totals': {},
        'family_statistics': {}
    }
    
    engine_poor = IntelligenceEngine(relays_poor_data)
    analysis_poor = engine_poor.analyze_all_layers()
    contact_intel_poor = analysis_poor['contact_intelligence']['template_optimized']['test_contact']
    
    print(f"\nPoor diversity test:")
    print(f"Network: {contact_intel_poor['portfolio_diversity']}")
    print(f"Geographic: {contact_intel_poor['geographic_risk']}")
    print(f"Infrastructure: {contact_intel_poor['infrastructure_risk']}")
    
    # Verify all show "Poor"
    assert 'Poor' in contact_intel_poor['portfolio_diversity'], "Network diversity should be Poor"
    assert 'Poor' in contact_intel_poor['geographic_risk'], "Geographic diversity should be Poor"
    assert 'Poor' in contact_intel_poor['infrastructure_risk'], "Infrastructure diversity should be Poor"
    
    # Test case 2: 2-3 AS, 2-3 countries, 2 platforms/versions (all Good)
    relays_good_data = {
        'relays': [
            {
                'fingerprint': 'B' * 40,
                'as_number': 12345,
                'country': 'us',
                'platform': 'Linux',
                'version': '0.4.7.8',
                'observed_bandwidth': 5000000,
                'consensus_weight': 1000
            },
            {
                'fingerprint': 'C' * 40,
                'as_number': 67890,
                'country': 'de',
                'platform': 'FreeBSD',
                'version': '0.4.6.8',
                'observed_bandwidth': 5000000,
                'consensus_weight': 1000
            }
        ],
        'sorted': {
            'contact': {
                'test_contact': {
                    'relays': [0, 1],
                    'unique_as_count': 2,  
                    'measured_count': 2
                }
            }
        },
        'network_totals': {},
        'family_statistics': {}
    }
    
    engine_good = IntelligenceEngine(relays_good_data)
    analysis_good = engine_good.analyze_all_layers()
    contact_intel_good = analysis_good['contact_intelligence']['template_optimized']['test_contact']
    
    print(f"\nGood diversity test:")
    print(f"Network: {contact_intel_good['portfolio_diversity']}")
    print(f"Geographic: {contact_intel_good['geographic_risk']}")
    print(f"Infrastructure: {contact_intel_good['infrastructure_risk']}")
    
    # Verify all show "Good"
    assert 'Good' in contact_intel_good['portfolio_diversity'], "Network diversity should be Good"
    assert 'Good' in contact_intel_good['geographic_risk'], "Geographic diversity should be Good"
    assert 'Good' in contact_intel_good['infrastructure_risk'], "Infrastructure diversity should be Good"
    
    # Test case 3: 4+ AS, 4+ countries, 3+ platforms/versions (all Great)
    relays_great_data = {
        'relays': [
            {
                'fingerprint': 'D' * 40,
                'as_number': 11111,
                'country': 'us',
                'platform': 'Linux',
                'version': '0.4.7.8',
                'observed_bandwidth': 5000000,
                'consensus_weight': 1000
            },
            {
                'fingerprint': 'E' * 40,
                'as_number': 22222,
                'country': 'de',
                'platform': 'FreeBSD', 
                'version': '0.4.6.8',
                'observed_bandwidth': 5000000,
                'consensus_weight': 1000
            },
            {
                'fingerprint': 'F' * 40,
                'as_number': 33333,
                'country': 'fr',
                'platform': 'OpenBSD',
                'version': '0.4.5.8',
                'observed_bandwidth': 5000000,
                'consensus_weight': 1000
            },
            {
                'fingerprint': 'G' * 40,
                'as_number': 44444,
                'country': 'nl',
                'platform': 'Darwin',
                'version': '0.4.4.8',
                'observed_bandwidth': 5000000,
                'consensus_weight': 1000
            }
        ],
        'sorted': {
            'contact': {
                'test_contact': {
                    'relays': [0, 1, 2, 3],
                    'unique_as_count': 4,
                    'measured_count': 4
                }
            }
        },
        'network_totals': {},
        'family_statistics': {}
    }
    
    engine_great = IntelligenceEngine(relays_great_data)
    analysis_great = engine_great.analyze_all_layers()
    contact_intel_great = analysis_great['contact_intelligence']['template_optimized']['test_contact']
    
    print(f"\nGreat diversity test:")
    print(f"Network: {contact_intel_great['portfolio_diversity']}")
    print(f"Geographic: {contact_intel_great['geographic_risk']}")
    print(f"Infrastructure: {contact_intel_great['infrastructure_risk']}")
    
    # Verify all show "Great"
    assert 'Great' in contact_intel_great['portfolio_diversity'], "Network diversity should be Great"
    assert 'Great' in contact_intel_great['geographic_risk'], "Geographic diversity should be Great"
    assert 'Great' in contact_intel_great['infrastructure_risk'], "Infrastructure diversity should be Great"
    
    # Test format consistency
    print("\nTesting format consistency:")
    
    # All should start with rating, followed by comma, then details
    formats = [
        contact_intel_poor['portfolio_diversity'],
        contact_intel_poor['geographic_risk'],
        contact_intel_poor['infrastructure_risk'],
        contact_intel_good['portfolio_diversity'],
        contact_intel_good['geographic_risk'],
        contact_intel_good['infrastructure_risk'],
        contact_intel_great['portfolio_diversity'],
        contact_intel_great['geographic_risk'],
        contact_intel_great['infrastructure_risk']
    ]
    
    for fmt in formats:
        assert ',' in fmt, f"Format should include comma: {fmt}"
        rating = fmt.split(',')[0].strip()
        assert rating in ['Poor', 'Good', 'Great'], f"Invalid rating: {rating}"
        print(f"✓ {fmt}")
    
    print("\n✅ All diversity rating consistency tests passed!")
    print("✅ Format: [Rating], [Details] confirmed for all three metrics")
    print("✅ Poor (red), Good (yellow), Great (green) ratings working correctly")

if __name__ == "__main__":
    test_diversity_consistency() 