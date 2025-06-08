#!/usr/bin/env python3
"""
Test the updated diversity rating system with Okay instead of Good.
"""

import sys
import os
sys.path.append('.')

from allium.lib.intelligence_engine import IntelligenceEngine

def test_okay_rating():
    """Test that all three diversity metrics now use Okay instead of Good"""
    
    print("Testing Okay rating change...")
    
    # Test case with 2-3 AS, 2-3 countries, 2 platforms/versions (all should be Okay)
    relays_okay_data = {
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
    
    engine_okay = IntelligenceEngine(relays_okay_data)
    analysis_okay = engine_okay.analyze_all_layers()
    contact_intel_okay = analysis_okay['contact_intelligence']['template_optimized']['test_contact']
    
    print(f"\nOkay rating test:")
    print(f"Network: {contact_intel_okay['portfolio_diversity']}")
    print(f"Geographic: {contact_intel_okay['geographic_risk']}")
    print(f"Infrastructure: {contact_intel_okay['infrastructure_risk']}")
    
    # Verify all show "Okay"
    assert 'Okay' in contact_intel_okay['portfolio_diversity'], f"Network diversity should be Okay, got: {contact_intel_okay['portfolio_diversity']}"
    assert 'Okay' in contact_intel_okay['geographic_risk'], f"Geographic diversity should be Okay, got: {contact_intel_okay['geographic_risk']}"
    assert 'Okay' in contact_intel_okay['infrastructure_risk'], f"Infrastructure diversity should be Okay, got: {contact_intel_okay['infrastructure_risk']}"
    
    # Verify no "Good" remains
    assert 'Good' not in contact_intel_okay['portfolio_diversity'], "Should not contain 'Good'"
    assert 'Good' not in contact_intel_okay['geographic_risk'], "Should not contain 'Good'"
    assert 'Good' not in contact_intel_okay['infrastructure_risk'], "Should not contain 'Good'"
    
    print("\n✅ All diversity ratings successfully changed to Okay!")
    print("✅ No 'Good' ratings found - change completed successfully")

if __name__ == "__main__":
    test_okay_rating() 